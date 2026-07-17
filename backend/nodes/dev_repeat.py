"""
RepeatNode
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class RepeatNode(DeviceNode):
    TYPE = "device.repeat"
    TITLE = "Repeat"
    CATEGORY = "robotics"
    PARAMS = [
        {"key": "times", "label": "Repeat how many times", "type": "text", "default": "10"},
        {"key": "counter", "label": "Counter variable", "type": "text", "default": "i"},
    ]

    # the generator treats this specially: everything downstream of it is
    # wrapped in the for-loop it opens.
    IS_BLOCK = True

    def loop_open(self):
        c = self.p("counter", "i")
        t = str(self.p("times", "10")).strip()
        return [f"for (int {c} = 0; {c} < {t}; {c}++) {{"]

    def loop_close(self):
        return ["}"]


# --------------------------------------------------------------- BUTTON
