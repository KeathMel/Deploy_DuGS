"""
Go To State node — switch the state machine to another state.

Drop it inside a State's body. When the board reaches it, it changes which
state runs from now on:

    state = RUNNING;

Typically you put it after a button press or a condition:

    [State: MENU] -> [Button: pressed] -> [Go To State: RUNNING]

SETTINGS
========
target : the state to switch to (must match a State node's name)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class GoToStateNode(DeviceNode):
    TYPE = "device.goto_state"
    TITLE = "Go To State"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "target", "label": "Go to state", "type": "text", "default": "STATE_1"},
    ]

    def loop(self):
        raw = str(self.p("target", "STATE_1")).strip()
        target = "".join(c if (c.isalnum() or c == "_") else "_" for c in raw) or "STATE_1"
        return [f"state = {target};"]
