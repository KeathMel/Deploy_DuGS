"""
Switch node — routes each incoming item to one of several outputs.
Modelled on n8n's Switch node (v3).

TWO MODES
=========

mode = "rules"  (default)
    You define an ordered list of rules. Each rule has a condition
    (field / operator / value, just like the IF node) and maps to an
    output index. The FIRST rule that matches wins (unless
    `all_matching_outputs` is on, in which case the item is sent to the
    output of every rule it matches — n8n's "Send data to all matching
    outputs" toggle).

    Rules are stored as a JSON array in the `rules` param, e.g.:
        [
          {"field": "tier", "operator": "equals", "value": "gold",     "output": 0},
          {"field": "tier", "operator": "equals", "value": "platinum", "output": 1},
          {"field": "score","operator": "greater than", "value": 90,   "output": 2}
        ]

    The number of outputs is `num_outputs` (so the canvas can draw the
    right number of ports). Rule `output` indices should be < num_outputs.

mode = "expression"
    A single Python expression is evaluated against each item. Whatever
    integer it returns is used directly as the output index.
        expression = "$json.score // 20"   ->  72 yields output 3
    `$json` is available (the item's json dict); plain `json` is too.

FALLBACK  (n8n's "Fallback Output")
===================================
fallback = "none"    -> unmatched items are dropped              (default)
fallback = "extra"   -> unmatched items go to an EXTRA output    appended
                        after the numbered ones (index == num_outputs)
fallback = "zero"    -> unmatched items go to output 0

OUTPUT NAMING
=============
`output_names` (optional JSON array of strings) is metadata n8n shows as
port labels. The engine ignores it; it's surfaced for the canvas/UI.

Operators match the IF node exactly so behaviour is consistent.
"""
import re
from node_base import Node, resolve_expr


class SwitchNode(Node):
    TYPE = "logic.switch"
    TITLE = "Switch"
    CATEGORY = "logic"
    INPUTS = 1
    OUTPUTS = 4            # default port count; real count = num_outputs (+1 if fallback=extra)
    PARAMS = [
        {
            "key": "mode",
            "label": "Mode",
            "type": "select",
            "default": "rules",
            "options": ["rules", "expression"],
        },
        {
            "key": "num_outputs",
            "label": "Number of Outputs",
            "type": "number",
            "default": 4,
        },
        {
            "key": "rules",
            "label": "Rules (JSON: [{field, operator, value, output}])",
            "type": "json",
            "default": [
                {"field": "", "operator": "equals", "value": "", "output": 0},
            ],
        },
        {
            "key": "all_matching_outputs",
            "label": "Send to ALL matching outputs",
            "type": "bool",
            "default": False,
        },
        {
            "key": "expression",
            "label": "Expression -> output index (e.g. $json.score // 20)",
            "type": "text",
            "default": "",
        },
        {
            "key": "fallback",
            "label": "Fallback for unmatched",
            "type": "select",
            "default": "none",
            "options": ["none", "extra", "zero"],
        },
        {
            "key": "output_names",
            "label": "Output names (optional JSON array)",
            "type": "json",
            "default": [],
        },
    ]

    # --- operator table shared with the IF node -------------------------
    def _coerce(self, actual, cmp_val, compare_as):
        if compare_as == "number":
            try: actual = float(actual)
            except (TypeError, ValueError): pass
            try: cmp_val = float(cmp_val)
            except (TypeError, ValueError): pass
        elif compare_as == "string":
            actual = str(actual) if actual is not None else ""
            cmp_val = str(cmp_val) if cmp_val is not None else ""
        elif compare_as == "boolean":
            actual = bool(actual)
            cmp_val = str(cmp_val).lower() in ("true", "1", "yes") if isinstance(cmp_val, str) else bool(cmp_val)
        else:  # auto
            try:
                a2 = float(actual); c2 = float(cmp_val)
                actual, cmp_val = a2, c2
            except (TypeError, ValueError):
                pass
        return actual, cmp_val

    def _test(self, actual, op, cmp_val, j, field_name):
        if op == "equals":           return actual == cmp_val
        if op == "not equals":       return actual != cmp_val
        if op == "greater than":     return actual is not None and actual > cmp_val
        if op == "less than":        return actual is not None and actual < cmp_val
        if op == "greater or equal": return actual is not None and actual >= cmp_val
        if op == "less or equal":    return actual is not None and actual <= cmp_val
        if op == "contains":         return cmp_val in str(actual or "")
        if op == "not contains":     return cmp_val not in str(actual or "")
        if op == "exists":           return field_name in j
        if op == "not exists":       return field_name not in j
        if op == "is empty":         return actual in (None, "", [], {})
        if op == "is not empty":     return actual not in (None, "", [], {})
        if op == "regex match":
            try: return bool(re.search(str(cmp_val), str(actual or "")))
            except re.error: return False
        return False

    def _eval_rule(self, rule, j):
        field_expr = rule.get("field", "")
        op = rule.get("operator", "equals")
        value_expr = rule.get("value", "")
        compare_as = rule.get("type", "auto")

        if "{{" in str(field_expr):
            actual = resolve_expr(field_expr, j)
            field_name = str(field_expr).strip()
        else:
            field_name = str(field_expr).strip()
            actual = j.get(field_name)

        cmp_val = resolve_expr(value_expr, j) if isinstance(value_expr, str) else value_expr
        actual, cmp_val = self._coerce(actual, cmp_val, compare_as)
        return self._test(actual, op, cmp_val, j, field_name)

    # --- main -----------------------------------------------------------
    def run(self, items):
        mode = self.params.get("mode", "rules")
        try:
            num_out = int(self.params.get("num_outputs", 4) or 4)
        except (TypeError, ValueError):
            num_out = 4
        num_out = max(1, num_out)
        fallback = self.params.get("fallback", "none")

        # total physical output ports: numbered outputs, plus one extra if
        # fallback routes to its own port.
        total_ports = num_out + (1 if fallback == "extra" else 0)
        outputs = [[] for _ in range(total_ports)]

        rules = self.params.get("rules") or []
        if isinstance(rules, dict):
            rules = [rules]
        all_matching = bool(self.params.get("all_matching_outputs", False))
        expression = self.params.get("expression", "")

        for item in items:
            j = item.get("json", {})
            placed = False

            if mode == "expression":
                idx = self._eval_index(expression, j)
                if idx is not None and 0 <= idx < num_out:
                    outputs[idx].append(item)
                    placed = True
            else:  # rules
                for rule in rules:
                    try:
                        out_idx = int(rule.get("output", 0))
                    except (TypeError, ValueError):
                        out_idx = 0
                    if 0 <= out_idx < num_out and self._eval_rule(rule, j):
                        outputs[out_idx].append(item)
                        placed = True
                        if not all_matching:
                            break

            if not placed:
                if fallback == "extra":
                    outputs[num_out].append(item)      # the appended extra port
                elif fallback == "zero":
                    outputs[0].append(item)
                # fallback == "none": drop

        return outputs

    def _eval_index(self, expression, j):
        if not expression:
            return None
        expr = str(expression).strip()
        # strip optional {{ }} wrapper
        if expr.startswith("{{") and expr.endswith("}}"):
            expr = expr[2:-2].strip()
        # $json.field  ->  json["field"];  $json.a.b -> json["a"]["b"]
        # turn dotted $json access into subscript access so eval works
        def _sub(m):
            path = m.group(1)
            out = "json"
            for part in path.lstrip(".").split("."):
                if part:
                    out += f'.get("{part}")' if False else f'["{part}"]'
            return out
        py = re.sub(r"\$json((?:\.[A-Za-z0-9_]+)*)", _sub, expr)
        try:
            result = eval(py, {"__builtins__": {}}, {"json": j})
            return int(result)
        except Exception:
            return None
