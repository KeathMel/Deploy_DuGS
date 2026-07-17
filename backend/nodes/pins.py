"""
pins.py — the board's pin map node.

Declare every pin ONCE here with a name, then every other robotics node refers
to it BY NAME instead of hardcoding a number. Change the wiring or the board and
you only edit this one node.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


# ----------------------------------------------------------------- PINS
class PinsNode(DeviceNode):
    """The board's pin map. Declare every pin ONCE here with a name, then every
    other node refers to it BY NAME instead of hardcoding a number.

    Change the board or rewire it, and you only edit this one node — the whole
    sketch follows. This is the same thing you'd hand-write at the top of a
    sketch:

        const int SERVO_1 = 9;
        const int BUTTON  = 4;
        const int LED     = 13;

    The `pins` param is a JSON list of {name, pin}:

        [
          {"name": "SERVO_1", "pin": "9"},
          {"name": "BUTTON",  "pin": "4"},
          {"name": "LED",     "pin": "LED_BUILTIN"}
        ]

    `pin` is written EXACTLY as the board labels it (9, A0, D5, GPIO17,
    LED_BUILTIN...) and goes into the generated code verbatim.
    Then a Servo node's Pin field is just:  SERVO_1
    """
    TYPE = "device.pins"
    TITLE = "Pins"
    CATEGORY = "robotics"
    INPUTS = 0          # it's a declaration, not an action — nothing flows in
    OUTPUTS = 1
    PARAMS = [
        {
            "key": "pins",
            "label": "Pin map (JSON: [{name, pin}])",
            "type": "json",
            "default": [
                {"name": "SERVO_1", "pin": "9"},
                {"name": "BUTTON", "pin": "4"},
            ],
        },
        {
            "key": "board",
            "label": "Board (a note for you; not compiled)",
            "type": "text",
            "default": "Arduino Uno",
        },
    ]

    def _pairs(self):
        raw = self.params.get("pins") or []
        if isinstance(raw, dict):
            raw = [raw]
        out = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            pin = str(entry.get("pin", "")).strip()
            if not name or not pin:
                continue
            # make the name a safe C identifier
            safe = "".join(c if (c.isalnum() or c == "_") else "_" for c in name)
            out.append((safe, pin))
        return out

    def globals(self):
        board = str(self.p("board", "")).strip()
        lines = []
        if board:
            lines.append(f"// board: {board}")
        for name, pin in self._pairs():
            lines.append(f"const int {name} = {pin};")
        return lines

    def loop(self):
        return []   # declarations only, nothing happens per-loop
