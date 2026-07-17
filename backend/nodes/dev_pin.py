"""
PinNode
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class PinNode(DeviceNode):
    TYPE = "device.pin"
    TITLE = "Pin"
    CATEGORY = "robotics"
    PARAMS = [
        {"key": "pin", "label": "Pin (as labelled on the board)", "type": "text", "default": "13"},
        {"key": "mode", "label": "What it does", "type": "select",
         "default": "digital write",
         "options": ["digital write", "analog write (PWM)",
                     "digital read", "analog read"]},
        {"key": "value", "label": "Value (HIGH/LOW, or 0-255 for PWM)",
         "type": "text", "default": "HIGH"},
        {"key": "into", "label": "Read into variable (read modes)",
         "type": "text", "default": "reading"},
    ]

    def setup(self):
        m = self.p("mode", "digital write")
        pin = self.pin("pin", "13")
        if m in ("digital write", "analog write (PWM)"):
            return [f"pinMode({pin}, OUTPUT);"]
        if m == "digital read":
            return [f"pinMode({pin}, INPUT_PULLUP);"]
        return []   # analog read needs no pinMode

    def globals(self):
        m = self.p("mode", "digital write")
        if m in ("digital read", "analog read"):
            return [f"int {self.p('into', 'reading')} = 0;"]
        return []

    def loop(self):
        m = self.p("mode", "digital write")
        pin = self.pin("pin", "13")     # used exactly as typed (9, A0, D13...)
        val = str(self.p("value", "HIGH")).strip()
        into = self.p("into", "reading")
        if m == "digital write":
            return [f"digitalWrite({pin}, {val});"]
        if m == "analog write (PWM)":
            return [f"analogWrite({pin}, {val});"]
        if m == "digital read":
            return [f"{into} = digitalRead({pin});"]
        if m == "analog read":
            return [f"{into} = analogRead({pin});"]
        return []


# --------------------------------------------------------------- SCREEN
