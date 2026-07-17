"""
ButtonNode
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class ButtonNode(DeviceNode):
    TYPE = "device.button"
    TITLE = "Button"
    CATEGORY = "robotics"
    PARAMS = [
        {"key": "pin", "label": "Pin (as labelled on the board)", "type": "text", "default": "4"},
        {"key": "wait_for_press", "label": "Wait here until pressed",
         "type": "bool", "default": True},
        {"key": "into", "label": "Or store state in variable",
         "type": "text", "default": "btn"},
    ]

    def setup(self):
        return [f"pinMode({self.pin('pin', '4')}, INPUT_PULLUP);"]

    def globals(self):
        if not self.p("wait_for_press", True):
            return [f"int {self.p('into', 'btn')} = 0;"]
        return []

    def loop(self):
        pin = self.pin("pin", "4")
        if self.p("wait_for_press", True):
            return [
                f"while (digitalRead({pin}) == HIGH) {{ /* wait for press */ }}",
                "delay(200);   // debounce",
            ]
        return [f"{self.p('into', 'btn')} = (digitalRead({pin}) == LOW);"]
