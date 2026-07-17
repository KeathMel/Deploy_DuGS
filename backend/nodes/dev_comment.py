"""
Comment node — a label you drop on the canvas to mark sections of a graph.

It does nothing on the board. It just makes big graphs readable, the way you'd
write a heading in code. Whatever you type shows up as a // comment in the
generated sketch too, so the code stays labelled to match your graph.

    // ===== MENU: pick number of servos =====

SETTINGS
========
text : the note to show
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class CommentNode(DeviceNode):
    TYPE = "device.comment"
    TITLE = "Comment"
    CATEGORY = "robotics"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "text", "label": "Note", "type": "text", "default": "section"},
    ]

    def loop(self):
        txt = str(self.p("text", "")).strip()
        if not txt:
            return []
        return [f"// ===== {txt} ====="]
