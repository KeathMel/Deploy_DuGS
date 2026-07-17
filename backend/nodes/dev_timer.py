"""
A NON-BLOCKING wait, using millis().

    The Wait node uses delay(), which freezes the whole board — nothing else
    can happen, the screen can't update, buttons can't be read. That's fine for
    simple sketches but useless once you want a responsive UI.

    This node instead remembers a deadline and checks whether it has passed.
    It has two outputs:

        output 0  "done"      -> the time is up (runs once, then re-arms)
        output 1  "waiting"   -> not yet; carry on doing other things

    So the loop keeps spinning and the screen stays alive while the timer runs.

        Loop -> Timer(2000ms) --done----> close the servo
                     |
                     +--waiting--------> update the screen
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class TimerNode(DeviceNode):
    """A NON-BLOCKING wait, using millis().

    The Wait node uses delay(), which freezes the whole board — nothing else
    can happen, the screen can't update, buttons can't be read. That's fine for
    simple sketches but useless once you want a responsive UI.

    This node instead remembers a deadline and checks whether it has passed.
    It has two outputs:

        output 0  "done"      -> the time is up (runs once, then re-arms)
        output 1  "waiting"   -> not yet; carry on doing other things

    So the loop keeps spinning and the screen stays alive while the timer runs.

        Loop -> Timer(2000ms) --done----> close the servo
                     |
                     +--waiting--------> update the screen
    """
    TYPE = "device.timer"
    TITLE = "Timer"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 2          # [0] = done, [1] = still waiting
    IS_BRANCH = True     # compiles to an if/else, same as the If node

    PARAMS = [
        {"key": "name", "label": "Timer name", "type": "text", "default": "t1"},
        {"key": "ms", "label": "Duration (ms) — can be a variable",
         "type": "text", "default": "1000"},
        {"key": "autostart", "label": "Start it at power-on", "type": "bool",
         "default": True},
    ]

    def _var(self):
        raw = str(self.p("name", "t1")).strip()
        return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw)

    def globals(self):
        v = self._var()
        return [f"unsigned long {v}_due = 0;"]

    def setup(self):
        if self.p("autostart", True):
            v = self._var()
            ms = str(self.p("ms", "1000")).strip()
            return [f"{v}_due = millis() + ({ms});"]
        return []

    def condition(self):
        """True when the time is up."""
        return f"millis() >= {self._var()}_due"

    def rearm(self):
        """Line that restarts the timer after it fires."""
        v = self._var()
        ms = str(self.p("ms", "1000")).strip()
        return f"{v}_due = millis() + ({ms});"

    def loop(self):
        return []


# -------------------------------------------------------------- ENCODER
