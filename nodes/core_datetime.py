"""
Date / Time — get the current time, or shift and format a date.

mode = "now"
    Put the current date/time into a field.
mode = "add"
    Take a date field, add/subtract time, store the result.
mode = "format"
    Reformat a date field into a chosen string format.

Dates are handled as ISO strings (2026-07-16T13:45:00). `amount`/`unit` shift
by seconds, minutes, hours, or days (amount can be negative to go back).

format uses Python strftime, e.g. %Y-%m-%d or %H:%M.
"""
from datetime import datetime, timedelta
from node_base import Node


class DateTimeNode(Node):
    TYPE = "core.datetime"
    TITLE = "Date & Time"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "mode", "label": "Mode", "type": "select", "default": "now",
         "options": ["now", "add", "format"]},
        {"key": "field", "label": "Date field (add/format modes)", "type": "text", "default": "date"},
        {"key": "amount", "label": "Amount (add mode, can be negative)", "type": "number", "default": 1},
        {"key": "unit", "label": "Unit (add mode)", "type": "select", "default": "days",
         "options": ["seconds", "minutes", "hours", "days"]},
        {"key": "format", "label": "Format (format mode, strftime)", "type": "text",
         "default": "%Y-%m-%d %H:%M"},
        {"key": "into", "label": "Store result in field", "type": "text", "default": "result"},
    ]

    def _parse(self, s):
        if isinstance(s, datetime):
            return s
        try:
            return datetime.fromisoformat(str(s))
        except Exception:
            return datetime.now()

    def run(self, items):
        mode = self.params.get("mode", "now")
        field = (self.params.get("field") or "date").strip()
        into = (self.params.get("into") or "result").strip()
        out = []
        for it in items:
            j = dict(it.get("json", {}))
            if mode == "now":
                j[into] = datetime.now().isoformat(timespec="seconds")
            elif mode == "add":
                base = self._parse(j.get(field))
                try:
                    amt = float(self.params.get("amount", 1) or 0)
                except (TypeError, ValueError):
                    amt = 0
                unit = self.params.get("unit", "days")
                delta = timedelta(**{unit: amt})
                j[into] = (base + delta).isoformat(timespec="seconds")
            elif mode == "format":
                base = self._parse(j.get(field))
                fmt = self.params.get("format", "%Y-%m-%d %H:%M")
                try:
                    j[into] = base.strftime(fmt)
                except Exception:
                    j[into] = base.isoformat(timespec="seconds")
            out.append({"json": j})
        if not items:
            # allow a lone "now" with no input
            if mode == "now":
                return [{"json": {into: datetime.now().isoformat(timespec="seconds")}}]
        return out
