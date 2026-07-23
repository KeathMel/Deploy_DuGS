"""
Loop Over Items (Split in Batches) — a 1:1 port of n8n's Loop node.

HOW IT WORKS
============
The node takes the WHOLE incoming item list and holds onto it. Then:

  1. It sends the next BATCH out the "loop" output (output 0).
  2. The nodes after "loop" process that batch.
  3. You wire the last node of that chain BACK into the Loop node's input.
  4. The Loop node hands out the next batch. Repeat.
  5. When every item has been handed out, the Loop combines all the results it
     received back and emits them out the "done" output (output 1).

The loop terminates ITSELF once the items run out — you do NOT need an IF node
to stop it.

    Source ──> Loop ──loop(0)──> [ do work ] ──┐
                 ^                             │
                 └─────────────────────────────┘
                 │
                 └──done(1)──> [ runs once, with all results combined ]

SETTINGS
========
batch_size  : how many items to hand out per pass (n8n's "Batch Size").
              Set to 1 to process strictly one item at a time.
reset       : throw away state and start over from the incoming items.

CONTEXT (readable from other nodes)
===================================
    {{ $('Loop').context.currentRunIndex }}   -> 0, 1, 2, ... which pass we're on
    {{ $('Loop').context.noItemsLeft }}       -> true once the last batch is out

Items handed out on the loop output are also tagged:
    item.json._batch_index   -> which pass this item went out on
    item.json._batch_total   -> how many passes there will be in total
"""
from node_base import Node


class LoopNode(Node):
    TYPE = "core.loop"
    TITLE = "Loop Over Items"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 2          # [0] = "loop"  ,  [1] = "done"

    # tells the engine this node may execute more than once — that's what lets
    # the processing chain feed back into it for the next batch.
    ALLOW_RERUN = True

    PARAMS = [
        {
            "key": "batch_size",
            "label": "Batch Size",
            "type": "number",
            "default": 1,
        },
        {
            "key": "reset",
            "label": "Reset (start over from the incoming items)",
            "type": "bool",
            "default": False,
        },
        {
            "key": "add_metadata",
            "label": "Tag items with _batch_index / _batch_total",
            "type": "bool",
            "default": True,
        },
    ]

    def __init__(self, name, params=None):
        super().__init__(name, params)
        self._pending = None      # items still waiting to be handed out
        self._collected = []      # results fed back in from the loop body
        self._run_index = 0       # which pass we're on (n8n: currentRunIndex)
        self._started = False
        self._total_batches = 0

    @property
    def context(self):
        """Exposed so expressions can read {{ $('Loop').context.xxx }}"""
        return {
            "currentRunIndex": self._run_index,
            "noItemsLeft": bool(self._pending is not None and not self._pending),
        }

    def run(self, items):
        try:
            size = int(self.params.get("batch_size", 1) or 1)
        except (TypeError, ValueError):
            size = 1
        size = max(1, size)
        add_meta = bool(self.params.get("add_metadata", True))
        reset = bool(self.params.get("reset", False))

        if reset:
            self._pending = None
            self._collected = []
            self._run_index = 0
            self._started = False

        # ---- FIRST ENTRY: swallow the incoming list and start batching ----
        if not self._started:
            self._pending = list(items)
            self._collected = []
            self._run_index = 0
            self._started = True
            self._total_batches = (len(self._pending) + size - 1) // size if self._pending else 0
        else:
            # ---- RE-ENTRY: these items came back from the loop body ----
            self._collected.extend(items)

        # ---- nothing left? finished: emit everything on the "done" output ----
        if not self._pending:
            done_items = list(self._collected)
            # reset so the node can be reused on a later run
            self._started = False
            self._pending = None
            self._collected = []
            self._run_index = 0
            print(f"    [loop] finished — {len(done_items)} item(s) out the 'done' output")
            return [[], done_items]        # port 0 = loop (empty), port 1 = done

        # ---- hand out the next batch on the "loop" output ----
        batch = self._pending[:size]
        self._pending = self._pending[size:]

        out = []
        for it in batch:
            if add_meta:
                j = dict(it.get("json", {}))
                j["_batch_index"] = self._run_index
                j["_batch_total"] = self._total_batches
                new_item = dict(it); new_item["json"] = j
                out.append(new_item)
            else:
                out.append(it)

        print(f"    [loop] pass {self._run_index}: sending {len(out)} item(s), "
              f"{len(self._pending)} left")
        self._run_index += 1

        return [out, []]                   # port 0 = loop (batch), port 1 = done (empty)
