"""
Split in Batches node — groups incoming items into chunks of N.

Why you want this: if a node upstream produces 100 items, every downstream node
processes all 100 at once. With an AI node or an HTTP request that means 100
simultaneous calls, which will get you rate-limited. This node lets you push
items through in controlled groups instead.

MODES
=====
mode = "batches"   (default)
    Emit the items regrouped into chunks of `batch_size`. The output is still
    a flat item list, but items carry batch metadata so downstream nodes (and
    you) can tell which batch they belong to:
        item.json._batch        -> batch index (0, 1, 2, ...)
        item.json._batch_size   -> how many items are in that batch
        item.json._batch_total  -> total number of batches
    This keeps the engine's one-pass model intact (no looping back), while
    still giving you the grouping.

mode = "first_batch"
    Emit ONLY the first `batch_size` items and drop the rest. Handy for
    testing a flow against a small sample before running the whole set.

mode = "single_item"
    Emit only one item (the one at `index`). Useful for debugging a specific
    record.

NOTE: this node does not loop back around the graph — it splits/limits the item
stream in a single pass. A true feedback loop needs engine support for
re-entering nodes, which is a separate change.
"""
from node_base import Node


class BatchNode(Node):
    TYPE = "core.batch"
    TITLE = "Split in Batches"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {
            "key": "mode",
            "label": "Mode",
            "type": "select",
            "default": "batches",
            "options": ["batches", "first_batch", "single_item"],
        },
        {
            "key": "batch_size",
            "label": "Batch size",
            "type": "number",
            "default": 10,
        },
        {
            "key": "index",
            "label": "Item index (single_item mode)",
            "type": "number",
            "default": 0,
        },
        {
            "key": "add_metadata",
            "label": "Add _batch info to each item",
            "type": "bool",
            "default": True,
        },
    ]

    def run(self, items):
        mode = self.params.get("mode", "batches")
        try:
            size = int(self.params.get("batch_size", 10) or 10)
        except (TypeError, ValueError):
            size = 10
        size = max(1, size)
        add_meta = bool(self.params.get("add_metadata", True))

        if not items:
            return []

        if mode == "single_item":
            try:
                idx = int(self.params.get("index", 0) or 0)
            except (TypeError, ValueError):
                idx = 0
            if 0 <= idx < len(items):
                return [items[idx]]
            return []

        if mode == "first_batch":
            return list(items[:size])

        # mode == "batches": regroup into chunks, tagging each item
        total_batches = (len(items) + size - 1) // size
        out = []
        for b in range(total_batches):
            chunk = items[b * size:(b + 1) * size]
            for it in chunk:
                if add_meta:
                    j = dict(it.get("json", {}))
                    j["_batch"] = b
                    j["_batch_size"] = len(chunk)
                    j["_batch_total"] = total_batches
                    new_item = dict(it); new_item["json"] = j
                    out.append(new_item)
                else:
                    out.append(it)
        return out
