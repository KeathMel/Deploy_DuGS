"""
ServoNode
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class ServoNode(DeviceNode):
    TYPE = "device.servo"
    TITLE = "Servo"
    CATEGORY = "robotics"
    PARAMS = [
        {"key": "pin", "label": "Pin (as labelled on the board)", "type": "text", "default": "9"},
        {"key": "angle", "label": "Angle (0-180)", "type": "number", "default": 90},
        {"key": "hold_ms", "label": "Hold after moving (ms, 0 = none)",
         "type": "number", "default": 0},
    ]

    def _var(self):
        return f"servo_{self.pin_var('pin', '9')}"

    def includes(self):
        return ["#include <Servo.h>"]

    def globals(self):
        return [f"Servo {self._var()};"]

    def setup(self):
        return [f"{self._var()}.attach({self.pin('pin', '9')});",
                f"{self._var()}.write(0);"]

    def loop(self):
        lines = [f"{self._var()}.write({self.num('angle', 90)});"]
        hold = self.num("hold_ms", 0)
        if hold:
            lines.append(f"delay({hold});")
        return lines


# ------------------------------------------------------------------ PIN
