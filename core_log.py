"""
Log node: prints each item to the terminal, passes them through unchanged.
Useful for debugging what's flowing through the pipeline.
"""
import json
from node_base import Node


class LogNode(Node):
    TYPE = "core.log"
    TITLE = "Log"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "label", "label": "Label", "type": "text", "default": "LOG"},
        {
            "key": "level",
            "label": "Level",
            "type": "select",
            "default": "info",
            "options": ["info", "debug", "warn", "error"],
        },
        {"key": "show_all_fields", "label": "Show all fields", "type": "bool", "default": True},
        {"key": "field", "label": "Field to show (if not all)", "type": "text", "default": ""},
    ]

    def run(self, items):
        label = self.params.get("label") or "LOG"
        level = (self.params.get("level") or "info").upper()
        show_all = self.params.get("show_all_fields", True)
        field = self.params.get("field", "").strip()

        for i, item in enumerate(items):
            j = item.get("json", {})
            if show_all or not field:
                payload = json.dumps(j, indent=2)
            else:
                payload = json.dumps(j.get(field), indent=2)
            print(f"  [{level}] [{label}] item {i}: {payload}")
        return items  # always pass through
