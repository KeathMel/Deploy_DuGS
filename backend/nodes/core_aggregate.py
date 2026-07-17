"""
Aggregate — the opposite of Split Out: combine many items into ONE.

Two modes:

mode = "into_list"  (default)
    Collect a field from every item into one array on a single output item:
        3 items each with {"id": ...}  ->  one item { "ids": [1, 2, 3] }

mode = "all_items"
    Put the whole set of items into one field:
        3 items  ->  one item { "items": [ {...}, {...}, {...} ] }

Handy before an HTTP request that wants a single JSON body, or to count/collect
results at the end of a branch.

SETTINGS
========
mode   : into_list or all_items
field  : (into_list) which field to collect from each item
into   : the output field name to store the collected array in
"""
from node_base import Node


class AggregateNode(Node):
    TYPE = "core.aggregate"
    TITLE = "Aggregate"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "mode", "label": "Mode", "type": "select", "default": "into_list",
         "options": ["into_list", "all_items"]},
        {"key": "field", "label": "Field to collect (into_list mode)",
         "type": "text", "default": "id"},
        {"key": "into", "label": "Store collected array in field",
         "type": "text", "default": "items"},
    ]

    def run(self, items):
        mode = self.params.get("mode", "into_list")
        into = (self.params.get("into") or "items").strip()
        if mode == "all_items":
            collected = [it.get("json", {}) for it in items]
        else:
            field = (self.params.get("field") or "id").strip()
            collected = []
            for it in items:
                j = it.get("json", {})
                if field in j:
                    collected.append(j[field])
        return [{"json": {into: collected, "count": len(collected)}}]
