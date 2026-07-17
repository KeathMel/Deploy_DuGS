"""
Array node — a numbered list of values you can index with a variable.

A plain Variable node holds ONE number. An Array holds many, and you can pick
one out with another variable:

    order[passIdx]        <- the 3rd item, if passIdx is 2
    servos[pick].write(90)

That indirection is what lets you say "open whichever servo was picked" instead
of hardcoding one.

SETTINGS
========
name    : the array's name (e.g. order, shotTimes)
size    : how many slots it has
values  : optional starting values, comma separated (e.g. 9, 10, 11, 12).
          Leave blank and every slot starts at 0.
type    : int (whole numbers) or bool (true/false flags)

USING IT
========
Anywhere a node takes a variable or a value, you can write an indexed lookup:

    Variable node:  name = pick        value = order[passIdx]
    If node:        left = isOpen[i]   right = 1
    Servo node:     pin  = SERVO_PINS[pick]

The Array Set node writes into a slot.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class ArrayNode(DeviceNode):
    TYPE = "device.array"
    TITLE = "Array"
    CATEGORY = "robotics"
    INPUTS = 0          # a declaration, like Pins — nothing flows in
    OUTPUTS = 1
    PARAMS = [
        {"key": "name", "label": "Array name", "type": "text", "default": "myList"},
        {"key": "size", "label": "How many slots", "type": "number", "default": 4},
        {"key": "values", "label": "Starting values (comma separated, optional)",
         "type": "text", "default": ""},
        {"key": "type", "label": "Type", "type": "select", "default": "int",
         "options": ["int", "bool", "long"]},
    ]

    def _name(self):
        raw = str(self.p("name", "myList")).strip()
        return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw)

    def globals(self):
        n = self._name()
        ctype = self.p("type", "int")
        raw = str(self.p("values", "")).strip()
        try:
            size = int(float(self.p("size", 4)))
        except (TypeError, ValueError):
            size = 4
        size = max(1, size)

        if raw:
            vals = [v.strip() for v in raw.split(",") if v.strip()]
            # pad or trim to the declared size
            while len(vals) < size:
                vals.append("0" if ctype != "bool" else "false")
            vals = vals[:size]
            joined = ", ".join(vals)
            return [f"{ctype} {n}[{size}] = {{{joined}}};"]
        zero = "false" if ctype == "bool" else "0"
        joined = ", ".join([zero] * size)
        return [f"{ctype} {n}[{size}] = {{{joined}}};"]

    def loop(self):
        return []   # declaration only
