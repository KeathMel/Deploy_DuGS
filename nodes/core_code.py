"""
Code node: run custom Python against each item.

Your code has access to:
  item    — the current item dict  ({"json": {...}})
  items   — ALL items (the full list)
  json    — shortcut for item["json"]
  result  — set this to your output item(s), or return via `result`

Modes:
  "run once"     — your code runs ONCE, gets `items`, sets `result` (a list)
  "run per item" — your code runs once PER item, gets `item` and `json`,
                   sets `result` (a single item dict OR a plain dict)

Example (run per item):
  result = {"json": {**json, "doubled": json["count"] * 2}}

Example (run once):
  result = [{"json": {"total": sum(i["json"]["price"] for i in items)}}]
"""
from node_base import Node


class CodeNode(Node):
    TYPE = "core.code"
    TITLE = "Code"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {
            "key": "mode",
            "label": "Run mode",
            "type": "select",
            "default": "run per item",
            "options": ["run per item", "run once"],
        },
        {
            "key": "code",
            "label": "Python code",
            "type": "multiline",
            "default": "# item / json / items available\nresult = item",
        },
    ]

    def run(self, items):
        code = (self.params.get("code") or "").strip()
        if not code:
            return items
        mode = self.params.get("mode", "run per item")

        if mode == "run once":
            scope = {"items": items, "result": None}
            exec(code, {}, scope)
            result = scope.get("result")
            if result is None:
                return items
            return self._normalise_list(result)
        else:
            out = []
            for item in items:
                j = item.get("json", {})
                scope = {"item": item, "json": j, "items": items, "result": None}
                exec(code, {}, scope)
                result = scope.get("result")
                if result is None:
                    out.append(item)
                elif isinstance(result, list):
                    out.extend(self._normalise_list(result))
                elif isinstance(result, dict):
                    if "json" in result:
                        out.append(result)
                    else:
                        out.append({"json": result})
            return out

    def _normalise_list(self, lst):
        out = []
        for r in lst:
            if isinstance(r, dict) and "json" in r:
                out.append(r)
            elif isinstance(r, dict):
                out.append({"json": r})
        return out
