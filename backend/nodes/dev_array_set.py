"""
Array Set node — write a value into one slot of an Array.

    order[i] = 3;
    isOpen[pick] = true;
    servos[pick].write(OPEN);      <- use the Servo node with pin = SERVO_PINS[pick]

SETTINGS
========
array  : which array to write into (its name)
index  : which slot — a number (2) or a variable (pick, i, passIdx)
op     : set / add / subtract
value  : what to write — a number, a variable, or another indexed lookup
         (e.g. order[j])

The index and value go into the code verbatim, so anything valid in C++ works.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class ArraySetNode(DeviceNode):
    TYPE = "device.array_set"
    TITLE = "Array Set"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "array", "label": "Array name", "type": "text", "default": "myList"},
        {"key": "index", "label": "Slot (number or variable)", "type": "text", "default": "0"},
        {"key": "op", "label": "Operation", "type": "select", "default": "set",
         "options": ["set", "add", "subtract"]},
        {"key": "value", "label": "Value (number / variable / expression)",
         "type": "text", "default": "0"},
    ]

    def loop(self):
        arr = str(self.p("array", "myList")).strip()
        idx = str(self.p("index", "0")).strip()
        val = str(self.p("value", "0")).strip()
        op = self.p("op", "set")
        slot = f"{arr}[{idx}]"
        if op == "add":
            return [f"{slot} += {val};"]
        if op == "subtract":
            return [f"{slot} -= {val};"]
        return [f"{slot} = {val};"]
