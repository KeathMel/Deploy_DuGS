"""
Wait node: pauses execution for a configurable duration.
"""
import time
from node_base import Node


class WaitNode(Node):
    TYPE = "core.wait"
    TITLE = "Wait"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "seconds", "label": "Seconds", "type": "number", "default": 1},
        {
            "key": "unit",
            "label": "Unit",
            "type": "select",
            "default": "seconds",
            "options": ["milliseconds", "seconds", "minutes"],
        },
    ]

    def run(self, items):
        seconds = float(self.params.get("seconds", 1) or 1)
        unit = self.params.get("unit", "seconds")
        if unit == "milliseconds":
            seconds = seconds / 1000
        elif unit == "minutes":
            seconds = seconds * 60
        time.sleep(seconds)
        return items
