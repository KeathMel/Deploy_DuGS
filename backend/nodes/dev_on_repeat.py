"""
Runs OVER AND OVER, forever (Arduino loop()).

    This is the main body of the sketch. Anything wired off here repeats
    endlessly while the board is powered.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class OnRepeatNode(DeviceNode):
    """Runs OVER AND OVER, forever (Arduino loop()).

    This is the main body of the sketch. Anything wired off here repeats
    endlessly while the board is powered.
    """
    TYPE = "device.on_repeat"
    TITLE = "On Repeat"
    CATEGORY = "robotics"
    INPUTS = 0
    OUTPUTS = 1
    IS_TRIGGER = True
    BLOCK = "loop"       # everything downstream compiles into loop()
    PARAMS = []

    def loop(self):
        return []


# ---------------------------------------------------------------- SERVO
