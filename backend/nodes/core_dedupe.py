"""
Remove Duplicates — drop items that repeat.

    field : which field decides "same". Leave blank to compare the whole item.

Keeps the FIRST occurrence of each, drops later repeats.
"""
import json as _json
from node_base import Node


class DedupeNode(Node):
    TYPE = "core.dedupe"
    TITLE = "Remove Duplicates"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "field", "label": "Compare by field (blank = whole item)",
         "type": "text", "default": ""},
    ]

    def run(self, items):
        field = (self.params.get("field") or "").strip()
        seen = set()
        out = []
        for it in items:
            j = it.get("json", {})
            if field:
                key = _json.dumps(j.get(field), sort_keys=True, default=str)
            else:
                key = _json.dumps(j, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out
