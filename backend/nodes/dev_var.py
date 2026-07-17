"""
VarNode
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class VarNode(DeviceNode):
    TYPE = "device.var"
    TITLE = "Variable"
    CATEGORY = "robotics"
    PARAMS = [
        {"key": "name", "label": "Variable name", "type": "text", "default": "count"},
        {"key": "op", "label": "Operation", "type": "select",
         "default": "set", "options": ["set", "add", "subtract"]},
        {"key": "value", "label": "Value", "type": "text", "default": "0"},
    ]

    def globals(self):
        return [f"int {self.p('name', 'count')} = 0;"]

    def loop(self):
        n = self.p("name", "count")
        v = str(self.p("value", "0")).strip()
        op = self.p("op", "set")
        if op == "add":
            return [f"{n} += {v};"]
        if op == "subtract":
            return [f"{n} -= {v};"]
        return [f"{n} = {v};"]


# --------------------------------------------------------------- REPEAT
