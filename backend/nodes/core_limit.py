"""
Limit — keep only the first (or last) N items, drop the rest.

    count : how many to keep
    from  : keep them from the start or the end of the list
"""
from node_base import Node


class LimitNode(Node):
    TYPE = "core.limit"
    TITLE = "Limit"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "count", "label": "Keep how many", "type": "number", "default": 10},
        {"key": "from", "label": "From", "type": "select", "default": "start",
         "options": ["start", "end"]},
    ]

    def run(self, items):
        try:
            n = int(self.params.get("count", 10) or 10)
        except (TypeError, ValueError):
            n = 10
        n = max(0, n)
        if self.params.get("from", "start") == "end":
            return items[-n:] if n else []
        return items[:n]
