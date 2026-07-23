"""
Split Out — turn one item with a list field into many items.

If an item looks like:
    { "name": "cart", "products": [ {"id":1}, {"id":2}, {"id":3} ] }

Split Out on "products" gives you THREE items:
    {"id":1}   {"id":2}   {"id":3}

This is how you fan a single record's array out so downstream nodes process
each element on its own.

SETTINGS
========
field       : the field holding the list (supports {{ }})
keep_parent : if on, each output item also keeps the other fields from the
              parent (minus the split field), so you don't lose context.
"""
from node_base import Node


class SplitOutNode(Node):
    TYPE = "core.split_out"
    TITLE = "Split Out"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "field", "label": "List field to split", "type": "text", "default": "data"},
        {"key": "keep_parent", "label": "Keep the other fields on each item",
         "type": "bool", "default": False},
    ]

    def run(self, items):
        field = (self.params.get("field") or "data").strip()
        keep = bool(self.params.get("keep_parent", False))
        out = []
        for item in items:
            j = item.get("json", {})
            val = self.rexpr("{{ $json." + field + " }}", j) if "{{" not in field else self.rexpr(field, j)
            if not isinstance(val, list):
                # not a list — pass the item through untouched
                out.append(item)
                continue
            parent = {k: v for k, v in j.items() if k != field} if keep else {}
            for element in val:
                if isinstance(element, dict):
                    merged = {**parent, **element} if keep else element
                else:
                    merged = {**parent, "value": element} if keep else {"value": element}
                out.append({"json": merged})
        return out
