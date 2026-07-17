"""
Servo Array node — a whole bank of servos you can address by index.

The plain Servo node drives ONE servo on ONE fixed pin. That's no good when you
want "open whichever servo was randomly picked" — for that you need an array of
servos and a variable index:

    servos[pick].write(OPEN);

This node declares the bank and attaches every servo in setup(). Then the
'Servo Move' node writes an angle to whichever slot you name.

SETTINGS
========
name   : the bank's name (default: servos)
pins   : the pins, comma separated, in order — e.g.  9, 10, 11, 12
         Slot 0 is the first pin, slot 1 the second, and so on.
         Names from the Pins node work too: SERVO_1, SERVO_2
start  : angle every servo is set to at power-on (usually the closed position)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class ServoArrayNode(DeviceNode):
    TYPE = "device.servo_array"
    TITLE = "Servo Array"
    CATEGORY = "robotics"
    INPUTS = 0          # a declaration, like Pins / Array
    OUTPUTS = 1
    PARAMS = [
        {"key": "name", "label": "Bank name", "type": "text", "default": "servos"},
        {"key": "pins", "label": "Pins in order (comma separated)",
         "type": "text", "default": "9, 10, 11, 12"},
        {"key": "start", "label": "Angle at power-on", "type": "number", "default": 0},
    ]

    def _name(self):
        raw = str(self.p("name", "servos")).strip()
        return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw)

    def _pins(self):
        raw = str(self.p("pins", "")).strip()
        return [p.strip() for p in raw.split(",") if p.strip()]

    def includes(self):
        return ["#include <Servo.h>"]

    def globals(self):
        n = self._name()
        pins = self._pins()
        count = max(1, len(pins))
        joined = ", ".join(pins) if pins else "9"
        return [
            f"const int {n}_COUNT = {count};",
            f"const int {n}_PINS[{count}] = {{{joined}}};",
            f"Servo {n}[{count}];",
        ]

    def setup(self):
        n = self._name()
        start = self.num("start", 0)
        return [
            f"for (int _i = 0; _i < {n}_COUNT; _i++) {{",
            f"  {n}[_i].attach({n}_PINS[_i]);",
            f"  {n}[_i].write({start});",
            "}",
        ]

    def loop(self):
        return []   # declaration only
