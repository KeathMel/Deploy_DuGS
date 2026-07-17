"""
Servo Move node — move ONE servo out of a Servo Array, chosen by index.

    servos[pick].write(90);

This is the node that makes "open whichever target was randomly picked"
possible. The index can be a number (2) or a variable (pick, i, openIdx).

SETTINGS
========
bank   : which Servo Array to drive (its name, e.g. servos)
index  : which slot — a number or a variable
angle  : the angle to move to (number or variable, e.g. OPEN / CLOSED / 90)
hold_ms: optional blocking pause after moving (0 = none). Prefer a Timer node
         instead if you want the board to stay responsive.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class ServoMoveNode(DeviceNode):
    TYPE = "device.servo_move"
    TITLE = "Servo Move"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "bank", "label": "Servo Array name", "type": "text", "default": "servos"},
        {"key": "index", "label": "Slot (number or variable)", "type": "text", "default": "0"},
        {"key": "angle", "label": "Angle (number or variable)", "type": "text", "default": "90"},
        {"key": "hold_ms", "label": "Hold after moving (ms, 0 = none)",
         "type": "number", "default": 0},
    ]

    def loop(self):
        bank = str(self.p("bank", "servos")).strip()
        idx = str(self.p("index", "0")).strip()
        angle = str(self.p("angle", "90")).strip()
        lines = [f"{bank}[{idx}].write({angle});"]
        hold = self.num("hold_ms", 0)
        if hold:
            lines.append(f"delay({hold});")
        return lines
