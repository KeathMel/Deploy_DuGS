"""
device_base.py — base class for HARDWARE nodes (servo projects).

A normal DUGS node runs Python on your PC. A device node is different: it does
not run at all — it EMITS ARDUINO C++ CODE. The workflow graph gets compiled
into a .ino sketch that you upload to the board, so the board runs standalone.

Each device node can contribute to four parts of the sketch:

    includes()   -> #include lines            (e.g. #include <Servo.h>)
    globals()    -> global declarations       (e.g. Servo servo9;)
    setup()      -> lines inside setup()      (e.g. servo9.attach(9);)
    loop()       -> lines inside loop()       (the node's actual action)

The generator walks the graph in execution order and stitches these together.
Duplicate includes/globals/setup lines are automatically de-duplicated, so two
Servo nodes on the same pin don't emit the header twice.
"""


class DeviceNode:
    TYPE = "device.base"
    TITLE = "Device"
    CATEGORY = "device"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = []

    # marks this as a code-generating node (servo projects only)
    IS_DEVICE = True

    def __init__(self, name, params=None):
        self.name = name
        self.params = params or {}

    # ---- helpers -------------------------------------------------------
    def p(self, key, default=None):
        v = self.params.get(key, default)
        return default if v in (None, "") else v

    def pin(self, key="pin", default="9"):
        """The pin as WRITTEN ON THE BOARD, used verbatim in the generated code.

        Whatever you type goes straight through: 9, A0, D13, GPIO17, LED_BUILTIN.
        That means this works on any board — we never translate or guess, we
        just emit the name you gave. Only whitespace is stripped.
        """
        v = self.params.get(key, default)
        if v is None or v == "":
            v = default
        return str(v).strip()

    def pin_var(self, key="pin", default="9"):
        """A safe C++ identifier derived from the pin name, for naming objects.
        Pin 'A0' -> 'A0'; 'GPIO17' -> 'GPIO17'; '9' -> '9' (prefixed by caller)."""
        raw = self.pin(key, default)
        return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw)

    def num(self, key, default=0):
        try:
            v = float(self.p(key, default))
            return int(v) if v == int(v) else v
        except (TypeError, ValueError):
            return default

    # ---- code contributions (override these) ---------------------------
    def includes(self) -> list[str]:
        return []

    def globals(self) -> list[str]:
        return []

    def setup(self) -> list[str]:
        return []

    def loop(self) -> list[str]:
        """The lines this node contributes to the main loop, in graph order."""
        return []

    # device nodes never execute in the Python engine
    def run(self, items):
        return items
