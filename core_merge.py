"""
Merge node — combines items from multiple inputs into one output.
Modelled on n8n's Merge node (v3).

This is a MULTI-INPUT node. The engine delivers a list-of-lists to run():
    items = [ input0_items, input1_items, input2_items, ... ]
(one inner list per input port). The engine only calls run() once EVERY
connected input port has delivered — so Merge always sees all branches.

INPUTS
======
`num_inputs` controls how many input ports exist (2, 3, 4, ...). The
canvas draws that many input dots.

MODES  (n8n's "Mode")
=====================
mode = "append"            (default)
    Output every item from input 0, then every item from input 1, etc.
    (n8n: "Append")

mode = "combine_position"
    Pair items by position: item 0 of every input merged together into
    one item, item 1 of every input merged, etc. (n8n: "Combine ->
    Combine by Position"). `include_unpaired` decides whether leftover
    items from longer inputs are emitted on their own.

mode = "combine_fields"
    SQL-JOIN style. Join items across inputs on a shared field value.
    `field_input1` / `field_input2` name the key field on input 0 and
    input 1 respectively (n8n calls these "Fields to Match"). For 3+
    inputs the same field name is reused for inputs beyond the second.
    `join` selects keep-matches-only vs keep-everything:
        "inner"        -> only items that matched across inputs
        "left"         -> all of input 0; matched data from others merged in
        "outer"        -> everything; unmatched items pass through alone
    (n8n: "Combine -> Combine by Matching Fields", with the
     "Output Type" / join options.)

mode = "combine_all"
    Cross-join: every item of input 0 merged with every item of input 1
    (and so on) — the cartesian product. (n8n: "Combine -> Combine by
    All Possible Combinations".)

mode = "choose_branch"
    Don't actually merge data — just pass through ONE input's items
    (or, with "wait", emit an empty/▢ trigger once all inputs arrive).
    `branch` = which input index to forward. (n8n: "Choose Branch".)

When two items are merged into one, fields from the later input overwrite
same-named fields from the earlier input (n8n "prefer input 2"), unless
`clash` = "prefer_first".
"""
from node_base import Node


class MergeNode(Node):
    TYPE = "core.merge"
    TITLE = "Merge"
    CATEGORY = "core"
    INPUTS = 2            # default; real count = num_inputs
    OUTPUTS = 1
    PARAMS = [
        {
            "key": "mode",
            "label": "Mode",
            "type": "select",
            "default": "append",
            "options": [
                "append",
                "combine_position",
                "combine_fields",
                "combine_all",
                "choose_branch",
            ],
        },
        {
            "key": "num_inputs",
            "label": "Number of Inputs",
            "type": "number",
            "default": 2,
        },
        {
            "key": "include_unpaired",
            "label": "Include unpaired items (by position)",
            "type": "bool",
            "default": True,
        },
        {
            "key": "field_input1",
            "label": "Field to match — input 1",
            "type": "text",
            "default": "",
        },
        {
            "key": "field_input2",
            "label": "Field to match — input 2+",
            "type": "text",
            "default": "",
        },
        {
            "key": "join",
            "label": "Join type (combine by fields)",
            "type": "select",
            "default": "inner",
            "options": ["inner", "left", "outer"],
        },
        {
            "key": "clash",
            "label": "On field clash",
            "type": "select",
            "default": "prefer_last",
            "options": ["prefer_last", "prefer_first"],
        },
        {
            "key": "branch",
            "label": "Branch to keep (choose_branch)",
            "type": "number",
            "default": 0,
        },
    ]

    # --- helpers --------------------------------------------------------
    def _normalise_inputs(self, items):
        """Accept either the multi-port [[...],[...]] shape from the engine
        or a flat list (defensive: treat as a single input)."""
        if items and isinstance(items[0], list):
            ports = list(items)
        else:
            ports = [items]
        try:
            n = int(self.params.get("num_inputs", 2) or 2)
        except (TypeError, ValueError):
            n = 2
        n = max(1, n)
        # pad / trim to declared input count
        while len(ports) < n:
            ports.append([])
        return ports[:n] if len(ports) > n else ports

    def _merge_json(self, a, b):
        ja = dict(a.get("json", {}))
        jb = dict(b.get("json", {}))
        if self.params.get("clash", "prefer_last") == "prefer_first":
            merged = {**jb, **ja}
        else:
            merged = {**ja, **jb}
        out = {"json": merged}
        # carry binary if present
        if "binary" in a or "binary" in b:
            out["binary"] = {**a.get("binary", {}), **b.get("binary", {})}
        return out

    # --- main -----------------------------------------------------------
    def run(self, items):
        ports = self._normalise_inputs(items)
        mode = self.params.get("mode", "append")

        if mode == "append":
            return self._append(ports)
        if mode == "combine_position":
            return self._combine_position(ports)
        if mode == "combine_fields":
            return self._combine_fields(ports)
        if mode == "combine_all":
            return self._combine_all(ports)
        if mode == "choose_branch":
            return self._choose_branch(ports)
        return self._append(ports)

    def _append(self, ports):
        out = []
        for p in ports:
            out.extend(p)
        return out

    def _combine_position(self, ports):
        include_unpaired = bool(self.params.get("include_unpaired", True))
        max_len = max((len(p) for p in ports), default=0)
        out = []
        for i in range(max_len):
            present = [p[i] for p in ports if i < len(p)]
            if len(present) < len(ports) and not include_unpaired:
                # at least one input has no item at this position -> skip
                continue
            merged = present[0]
            for nxt in present[1:]:
                merged = self._merge_json(merged, nxt)
            out.append(merged)
        return out

    def _combine_all(self, ports):
        # cartesian product across all non-empty inputs
        active = [p for p in ports if p]
        if not active:
            return []
        combos = [active[0][i] for i in range(len(active[0]))]
        result = list(active[0])
        for p in active[1:]:
            nxt = []
            for left in result:
                for right in p:
                    nxt.append(self._merge_json(left, right))
            result = nxt
        return result

    def _combine_fields(self, ports):
        f1 = str(self.params.get("field_input1", "")).strip()
        f2 = str(self.params.get("field_input2", "")).strip() or f1
        join = self.params.get("join", "inner")
        if not f1:
            # nothing to join on -> behave like append
            return self._append(ports)

        base = ports[0]
        result = list(base)
        matched_base = [False] * len(base)

        for p_idx in range(1, len(ports)):
            other = ports[p_idx]
            # index the other input by its key field value
            index = {}
            matched_other = [False] * len(other)
            for oi, o in enumerate(other):
                key = o.get("json", {}).get(f2)
                index.setdefault(key, []).append(oi)

            new_result = []
            for ri, left in enumerate(result):
                key = left.get("json", {}).get(f1)
                hits = index.get(key, [])
                if hits:
                    for oi in hits:
                        new_result.append(self._merge_json(left, other[oi]))
                        matched_other[oi] = True
                    if ri < len(matched_base):
                        matched_base[ri] = True
                else:
                    if join in ("left", "outer"):
                        new_result.append(left)
            # outer join: tack on unmatched items from the other input
            if join == "outer":
                for oi, o in enumerate(other):
                    if not matched_other[oi]:
                        new_result.append(o)
            result = new_result

        if join == "inner":
            # inner join already filtered (left-side non-matches were dropped
            # because join != left/outer), so result is correct.
            pass
        return result

    def _choose_branch(self, ports):
        try:
            b = int(self.params.get("branch", 0) or 0)
        except (TypeError, ValueError):
            b = 0
        if 0 <= b < len(ports):
            return list(ports[b])
        return []
