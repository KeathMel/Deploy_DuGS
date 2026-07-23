"""
Manual Trigger: starts the workflow. The 'data' param is the initial JSON
that flows into all downstream nodes.
"""
from node_base import Node, make_item


class ManualTrigger(Node):
    TYPE = "trigger.manual"
    TITLE = "Manual Trigger"
    CATEGORY = "trigger"
    INPUTS = 0
    OUTPUTS = 1
    PARAMS = [
        {"key": "data", "label": "Start Data (JSON)", "type": "json", "default": {"started": True}},
    ]

    def run(self, items):
        start_data = self.params.get("data") or {"started": True}
        if not isinstance(start_data, dict):
            start_data = {"value": start_data}
        return [make_item(start_data)]
