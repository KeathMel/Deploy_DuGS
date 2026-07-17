"""
Map node — rescale a number from one range to another (Arduino map/constrain).

Turns a value measured in one range into the matching value in another. The
classic use is a sensor or encoder reading:

    a knob reads 0..1023  ->  map it to an angle 0..180
    level 1..10           ->  map it to a delay 3000..500 ms  (note: high level = short delay)

    map(x, fromLow, fromHigh, toLow, toHigh)

With "clamp" on, the result is also held inside the to-range with constrain(),
so a slightly out-of-range input can't produce a silly output.

SETTINGS
========
input     : the value to convert (a variable or number)
from_low  / from_high : the range the input is currently in
to_low    / to_high   : the range you want it in
into      : variable to store the result
clamp     : keep the result within to_low..to_high
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class MapNode(DeviceNode):
    TYPE = "device.map"
    TITLE = "Map"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "input", "label": "Input value (variable or number)",
         "type": "text", "default": "reading"},
        {"key": "from_low", "label": "From low", "type": "text", "default": "0"},
        {"key": "from_high", "label": "From high", "type": "text", "default": "1023"},
        {"key": "to_low", "label": "To low", "type": "text", "default": "0"},
        {"key": "to_high", "label": "To high", "type": "text", "default": "180"},
        {"key": "into", "label": "Store result in variable", "type": "text", "default": "mapped"},
        {"key": "clamp", "label": "Clamp result to the to-range", "type": "bool", "default": True},
    ]

    def globals(self):
        return [f"int {self.p('into', 'mapped')} = 0;"]

    def loop(self):
        x = str(self.p("input", "reading")).strip()
        fl = str(self.p("from_low", "0")).strip()
        fh = str(self.p("from_high", "1023")).strip()
        tl = str(self.p("to_low", "0")).strip()
        th = str(self.p("to_high", "180")).strip()
        into = self.p("into", "mapped")
        expr = f"map({x}, {fl}, {fh}, {tl}, {th})"
        lines = [f"{into} = {expr};"]
        if self.p("clamp", True):
            # constrain needs low <= high; the to-range may be inverted
            # (e.g. 3000..500), so constrain against min/max of the two.
            lines.append(
                f"{into} = constrain({into}, min({tl}, {th}), max({tl}, {th}));")
        return lines
