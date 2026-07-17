"""
A rotary encoder (the wheel you turn).

    Reads the two encoder pins and gives you which way it turned:
        +1  turned right / clockwise
        -1  turned left / anticlockwise
         0  didn't move

    It writes that into a variable you name, and can optionally apply it
    straight to a setting variable with min/max clamping — which is what you
    almost always want:

        target = "servoCount", min = 1, max = 4

    means turning the wheel adjusts servoCount and keeps it between 1 and 4.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class EncoderNode(DeviceNode):
    """A rotary encoder (the wheel you turn).

    Reads the two encoder pins and gives you which way it turned:
        +1  turned right / clockwise
        -1  turned left / anticlockwise
         0  didn't move

    It writes that into a variable you name, and can optionally apply it
    straight to a setting variable with min/max clamping — which is what you
    almost always want:

        target = "servoCount", min = 1, max = 4

    means turning the wheel adjusts servoCount and keeps it between 1 and 4.
    """
    TYPE = "device.encoder"
    TITLE = "Encoder"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "pin_a", "label": "Pin A", "type": "text", "default": "2"},
        {"key": "pin_b", "label": "Pin B", "type": "text", "default": "3"},
        {"key": "into", "label": "Direction into variable (+1 / -1 / 0)",
         "type": "text", "default": "turn"},
        {"key": "target", "label": "Apply to setting variable (optional)",
         "type": "text", "default": ""},
        {"key": "min", "label": "Minimum (when applying)", "type": "text", "default": "0"},
        {"key": "max", "label": "Maximum (when applying)", "type": "text", "default": "10"},
    ]

    def globals(self):
        into = self.p("into", "turn")
        g = [f"int {into} = 0;",
             "int _encLastA = HIGH;"]
        tgt = str(self.p("target", "")).strip()
        if tgt:
            g.append(f"int {tgt} = 0;")
        return g

    def setup(self):
        return [f"pinMode({self.pin('pin_a', '2')}, INPUT_PULLUP);",
                f"pinMode({self.pin('pin_b', '3')}, INPUT_PULLUP);",
                f"_encLastA = digitalRead({self.pin('pin_a', '2')});"]

    def loop(self):
        a = self.pin("pin_a", "2")
        b = self.pin("pin_b", "3")
        into = self.p("into", "turn")
        lines = [
            "{",
            f"  int _a = digitalRead({a});",
            f"  {into} = 0;",
            "  if (_a != _encLastA && _a == LOW) {",
            f"    {into} = (digitalRead({b}) != _a) ? +1 : -1;",
            "  }",
            "  _encLastA = _a;",
            "}",
        ]
        tgt = str(self.p("target", "")).strip()
        if tgt:
            lo = str(self.p("min", "0")).strip()
            hi = str(self.p("max", "10")).strip()
            lines += [
                f"if ({into} != 0) {{",
                f"  {tgt} += {into};",
                f"  if ({tgt} < {lo}) {tgt} = {lo};",
                f"  if ({tgt} > {hi}) {tgt} = {hi};",
                "}",
            ]
        return lines


# ------------------------------------------------------------------- IF
