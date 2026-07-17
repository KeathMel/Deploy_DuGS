"""
Branch: run one chain if a condition is true, another if it's false.

    Compiles to a real C++ if/else:

        if (streak >= 2) {
          ... TRUE chain ...
        } else {
          ... FALSE chain ...
        }

    Output 0 = TRUE branch, output 1 = FALSE branch.

    `left` and `right` go straight into the code, so they can be a variable
    name (streak), a pin name (BUTTON), a number (2), a function call
    (digitalRead(BUTTON)) or an Arduino constant (HIGH, LOW).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class IfNode(DeviceNode):
    """Branch: run one chain if a condition is true, another if it's false.

    Compiles to a real C++ if/else:

        if (streak >= 2) {
          ... TRUE chain ...
        } else {
          ... FALSE chain ...
        }

    Output 0 = TRUE branch, output 1 = FALSE branch.

    `left` and `right` go straight into the code, so they can be a variable
    name (streak), a pin name (BUTTON), a number (2), a function call
    (digitalRead(BUTTON)) or an Arduino constant (HIGH, LOW).
    """
    TYPE = "device.if"
    TITLE = "If"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 2          # [0] = true, [1] = false
    IS_BRANCH = True

    PARAMS = [
        {"key": "left", "label": "Left side (variable / pin / number)",
         "type": "text", "default": "count"},
        {"key": "op", "label": "Compare", "type": "select", "default": ">=",
         "options": ["==", "!=", ">", "<", ">=", "<="]},
        {"key": "right", "label": "Right side (variable / number / HIGH / LOW)",
         "type": "text", "default": "1"},
    ]

    def condition(self):
        left = str(self.p("left", "count")).strip()
        op = str(self.p("op", ">=")).strip()
        right = str(self.p("right", "1")).strip()
        return f"{left} {op} {right}"

    def loop(self):
        return []   # the generator emits the if/else around the branches


# ------------------------------------------------------- TRIGGERS (start)
# An Arduino sketch has exactly two entry points:
#   setup()  runs ONCE when the board powers on
#   loop()   runs OVER AND OVER, forever, after setup finishes
# These two nodes are how you choose which one a chain belongs to. Wire your
# nodes off one of them and they compile into that block.
