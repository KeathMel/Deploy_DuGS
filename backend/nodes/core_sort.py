"""
Sort — reorder items by a field.

    field    : which field to sort on
    order    : ascending or descending
    numeric  : compare as numbers (so 10 > 9). Off = text compare.
"""
from node_base import Node


class SortNode(Node):
    TYPE = "core.sort"
    TITLE = "Sort"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "field", "label": "Sort by field", "type": "text", "default": "id"},
        {"key": "order", "label": "Order", "type": "select", "default": "ascending",
         "options": ["ascending", "descending"]},
        {"key": "numeric", "label": "Compare as numbers", "type": "bool", "default": True},
    ]

    def run(self, items):
        field = (self.params.get("field") or "id").strip()
        desc = self.params.get("order", "ascending") == "descending"
        numeric = bool(self.params.get("numeric", True))

        def key(it):
            v = it.get("json", {}).get(field)
            if numeric:
                try:
                    return (0, float(v))
                except (TypeError, ValueError):
                    return (1, 0)   # non-numbers sort after numbers
            return (0, str(v) if v is not None else "")

        try:
            return sorted(items, key=key, reverse=desc)
        except Exception:
            return items
