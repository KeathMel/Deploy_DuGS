"""
RandomNode
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class RandomNode(DeviceNode):
    TYPE = "device.random"
    TITLE = "Random"
    CATEGORY = "robotics"
    PARAMS = [
        {"key": "into", "label": "Store in variable", "type": "text", "default": "pick"},
        {"key": "min", "label": "Minimum", "type": "number", "default": 0},
        {"key": "max", "label": "Maximum", "type": "number", "default": 3},
    ]

    def globals(self):
        return [f"int {self.p('into', 'pick')} = 0;"]

    def setup(self):
        return ["randomSeed(analogRead(A0));"]

    def loop(self):
        lo, hi = self.num("min", 0), self.num("max", 3)
        return [f"{self.p('into', 'pick')} = random({lo}, {hi} + 1);"]


# ------------------------------------------------------------------ VAR
