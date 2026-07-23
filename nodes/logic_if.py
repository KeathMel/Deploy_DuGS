"""
IF node: routes items into two outputs based on a condition.
  output 0 (true branch)  — items that PASS the condition
  output 1 (false branch) — items that FAIL

Supports {{ $json.field }} expressions in the value param.

Operators:
  equals / not equals
  greater than / less than / greater or equal / less or equal
  contains / not contains (string)
  exists / not exists (field presence)
  is empty / is not empty
  regex match
"""
import re
from node_base import Node, resolve_expr


class IfNode(Node):
    TYPE = "logic.if"
    TITLE = "IF"
    CATEGORY = "logic"
    INPUTS = 1
    OUTPUTS = 2   # [true_branch, false_branch]
    PARAMS = [
        {"key": "field", "label": "Field (or {{ $json.x }})", "type": "text", "default": ""},
        {
            "key": "operator",
            "label": "Operator",
            "type": "select",
            "default": "equals",
            "options": [
                "equals",
                "not equals",
                "greater than",
                "less than",
                "greater or equal",
                "less or equal",
                "contains",
                "not contains",
                "exists",
                "not exists",
                "is empty",
                "is not empty",
                "regex match",
            ],
        },
        {"key": "value", "label": "Value (or {{ $json.x }})", "type": "text", "default": ""},
        {
            "key": "type",
            "label": "Compare as",
            "type": "select",
            "default": "auto",
            "options": ["auto", "string", "number", "boolean"],
        },
    ]

    def run(self, items):
        field_expr = self.params.get("field", "")
        op = self.params.get("operator", "equals")
        value_expr = self.params.get("value", "")
        compare_as = self.params.get("type", "auto")

        true_items, false_items = [], []
        for item in items:
            j = item.get("json", {})

            # resolve field: if it's an expression get the value, else do a dict lookup
            if "{{" in str(field_expr):
                actual = resolve_expr(field_expr, j)
            else:
                field_name = str(field_expr).strip()
                actual = j.get(field_name)

            # resolve comparison value
            cmp_val = resolve_expr(value_expr, j) if isinstance(value_expr, str) else value_expr

            # type coercion
            actual, cmp_val = self._coerce(actual, cmp_val, compare_as)

            passed = self._test(actual, op, cmp_val, j, field_expr)
            (true_items if passed else false_items).append(item)

        return [true_items, false_items]

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
        else:  # auto: try number coercion if both look numeric
            try:
                a2 = float(actual); c2 = float(cmp_val)
                actual, cmp_val = a2, c2
            except (TypeError, ValueError):
                pass
        return actual, cmp_val

    def _test(self, actual, op, cmp_val, j, field_expr):
        field_name = str(field_expr).strip()
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
