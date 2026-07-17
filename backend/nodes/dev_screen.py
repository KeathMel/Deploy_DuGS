"""
ScreenNode
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class ScreenNode(DeviceNode):
    TYPE = "device.screen"
    TITLE = "Screen"
    CATEGORY = "robotics"
    PARAMS = [
        {"key": "text", "label": "Text to show", "type": "text", "default": "HELLO"},
        {"key": "x", "label": "X position", "type": "number", "default": 20},
        {"key": "y", "label": "Y position", "type": "number", "default": 36},
        {"key": "size", "label": "Text size", "type": "select",
         "default": "medium", "options": ["small", "medium", "big"]},
        {"key": "clear", "label": "Clear screen first", "type": "bool", "default": True},
        {"key": "show_var", "label": "Show a variable instead (name, optional)",
         "type": "text", "default": ""},
    ]

    FONTS = {
        "small":  "u8g2_font_5x8_tr",
        "medium": "u8g2_font_6x12_tr",
        "big":    "u8g2_font_logisoso28_tn",
    }

    def includes(self):
        return ["#include <U8g2lib.h>", "#include <Wire.h>"]

    def globals(self):
        return ["U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);"]

    def setup(self):
        return ["u8g2.begin();"]

    def loop(self):
        lines = []
        if self.p("clear", True):
            lines.append("u8g2.clearBuffer();")
        font = self.FONTS.get(self.p("size", "medium"), self.FONTS["medium"])
        lines.append(f"u8g2.setFont({font});")
        x, y = self.num("x", 20), self.num("y", 36)
        var = str(self.p("show_var", "")).strip()
        if var:
            # print a variable's value
            lines.append("{ char _b[16]; sprintf(_b, \"%d\", " + var + ");")
            lines.append(f"  u8g2.drawStr({x}, {y}, _b); }}")
        else:
            txt = str(self.p("text", "")).replace('"', '\\"')
            lines.append(f'u8g2.drawStr({x}, {y}, "{txt}");')
        lines.append("u8g2.sendBuffer();")
        return lines


# ----------------------------------------------------------------- WAIT
