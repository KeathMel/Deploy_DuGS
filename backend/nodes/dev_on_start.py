"""
Runs ONCE when the board powers on (Arduino setup()).

    Use it for things that should happen a single time: opening a servo to its
    starting position, showing a splash screen, calibrating, seeding random.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device_base import DeviceNode


class OnStartNode(DeviceNode):
    """Runs ONCE when the board powers on (Arduino setup()).

    Use it for things that should happen a single time: opening a servo to its
    starting position, showing a splash screen, calibrating, seeding random.
    """
    TYPE = "device.on_start"
    TITLE = "On Start"
    CATEGORY = "robotics"
    INPUTS = 0
    OUTPUTS = 1
    IS_TRIGGER = True
    BLOCK = "setup"      # everything downstream compiles into setup()
    PARAMS = []

    def loop(self):
        return []
