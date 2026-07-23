"""
Set node: adds/overwrites fields on every item flowing through.

You can set fixed values OR use expressions like {{ $json.existingField }}.

Modes:
  "keep"    — keep all existing fields, add/overwrite only what you specify
  "replace" — output only the fields you define (wipe the rest)

Each assignment is defined as a list of {name, value} pairs via the
"assignments" param. The UI renders this as a JSON array:
  [{"name": "city", "value": "Oslo"}, {"name": "greeting", "value": "Hello {{ $json.name }}!"}]
"""
from node_base import Node


class SetNode(Node):
    TYPE = "core.set"
    TITLE = "Set"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {
            "key": "mode",
            "label": "Mode",
            "type": "select",
            "default": "keep",
            "options": ["keep", "replace"],
        },
        {
            "key": "assignments",
            "label": "Fields (JSON array: [{\"name\":\"key\",\"value\":\"val\"}])",
            "type": "json",
            "default": [{"name": "field", "value": "value"}],
        },
    ]

    def run(self, items):
        mode = self.params.get("mode", "keep")
        assignments = self.params.get("assignments") or []
        if isinstance(assignments, dict):
            # legacy: support old {"key": "value"} format
            assignments = [{"name": k, "value": v} for k, v in assignments.items()]

        out = []
        for item in items:
            j = item.get("json", {})
            new_json = {} if mode == "replace" else dict(j)
            for a in assignments:
                if not isinstance(a, dict):
                    continue
                name = a.get("name", "").strip()
                if not name:
                    continue
                raw_val = a.get("value")
                # resolve expressions against current item
                from node_base import resolve_expr
                val = resolve_expr(raw_val, j)
                new_json[name] = val
            out.append({"json": new_json})
        return out
