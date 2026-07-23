"""
Schedule trigger — fires a workflow automatically on a timer.

The node itself only DESCRIBES the schedule; the actual firing is done by the
scheduler loop inside api.py, which polls registered schedules and starts the
workflow when one is due. That means schedules only run while api.py is running.

MODES
=====
mode = "interval"  (default)
    Run every N of the chosen unit:
        every = 5, unit = "minutes"   -> every 5 minutes
        every = 2, unit = "hours"     -> every 2 hours
mode = "daily"
    Run once a day at a specific wall-clock time:
        at = "08:00"   -> every day at 8am (24h format, local time)

OUTPUT
======
When it fires, the trigger emits one item describing the run:
    {
      "triggered_at": "2026-06-24T08:00:00",
      "mode": "daily",
      "schedule": "08:00"
    }
"""
from datetime import datetime
from node_base import Node


class ScheduleTriggerNode(Node):
    TYPE = "trigger.schedule"
    TITLE = "Schedule"
    CATEGORY = "trigger"
    INPUTS = 0
    OUTPUTS = 1
    PARAMS = [
        {
            "key": "mode",
            "label": "Mode",
            "type": "select",
            "default": "interval",
            "options": ["interval", "daily"],
        },
        {
            "key": "every",
            "label": "Every (interval mode)",
            "type": "number",
            "default": 5,
        },
        {
            "key": "unit",
            "label": "Unit (interval mode)",
            "type": "select",
            "default": "minutes",
            "options": ["seconds", "minutes", "hours"],
        },
        {
            "key": "at",
            "label": "At time HH:MM (daily mode)",
            "type": "text",
            "default": "08:00",
        },
        {
            "key": "enabled",
            "label": "Enabled",
            "type": "bool",
            "default": True,
        },
    ]

    # --- helpers used by the scheduler in api.py -------------------------
    def interval_seconds(self):
        """How many seconds between runs (interval mode). None for daily."""
        if self.params.get("mode", "interval") != "interval":
            return None
        try:
            every = int(self.params.get("every", 5) or 5)
        except (TypeError, ValueError):
            every = 5
        every = max(1, every)
        unit = self.params.get("unit", "minutes")
        mult = {"seconds": 1, "minutes": 60, "hours": 3600}.get(unit, 60)
        return every * mult

    def daily_time(self):
        """(hour, minute) for daily mode, or None."""
        if self.params.get("mode", "interval") != "daily":
            return None
        raw = str(self.params.get("at", "08:00") or "08:00").strip()
        try:
            hh, mm = raw.split(":")
            return int(hh) % 24, int(mm) % 60
        except Exception:
            return 8, 0

    def run(self, items):
        mode = self.params.get("mode", "interval")
        if mode == "daily":
            hh, mm = self.daily_time()
            sched = f"{hh:02d}:{mm:02d}"
        else:
            sched = f"every {self.params.get('every', 5)} {self.params.get('unit', 'minutes')}"
        return [{"json": {
            "triggered_at": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "schedule": sched,
        }}]
