"""
State node — one screen / mode in a state machine.

Real projects with menus work as a state machine: the board is in ONE state at
a time (SERVO_SELECT, then SHOT_SELECT, then RUNNING...), and each loop it does
only that state's work. Turning a knob or pressing a button switches to the
next state.

A State node is one of those states. Everything wired off its output is that
state's body — it runs only while the machine is in this state. Use a
'Go To State' node inside the body to move to another state.

    [On Repeat] -> [State: MENU] --> ...menu code...  --> [Go To State: RUNNING]
                   [State: RUNNING] --> ...run code...

HOW IT COMPILES
===============
All the states in a graph compile into one switch, inside loop():

    switch (state) {
      case MENU:    ...; break;
      case RUNNING: ...; break;
    }

The FIRST state you place is the one the board starts in.

SETTINGS
========
name : the state's name (e.g. MENU, RUNNING, COUNTDOWN). UPPERCASE by habit.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class StateNode(DeviceNode):
    TYPE = "device.state"
    TITLE = "State"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 1
    IS_STATE = True     # the generator collects these into a switch()

    PARAMS = [
        {"key": "name", "label": "State name (e.g. MENU)", "type": "text",
         "default": "STATE_1"},
    ]

    def state_name(self):
        raw = str(self.p("name", "STATE_1")).strip()
        return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw) or "STATE_1"

    def loop(self):
        return []
