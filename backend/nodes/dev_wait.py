"""
WaitNode
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class WaitNode(DeviceNode):
    TYPE = "device.wait"
    TITLE = "Wait"
    CATEGORY = "robotics"
    PARAMS = [
        {"key": "ms", "label": "Wait (milliseconds)", "type": "number", "default": 1000},
    ]

    def loop(self):
        return [f"delay({self.num('ms', 1000)});"]


# --------------------------------------------------------------- RANDOM
