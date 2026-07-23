"""
node_base.py — the contract every node follows.

DATA SHAPE:
  Data passed between nodes is always a list of "items".
  Each item is a dict: {"json": {...}, "binary": {...}}  (binary optional)

EXPRESSION RESOLUTION:
  Any param value that is a string containing {{ ... }} gets interpolated
  against the current item's json. Examples:
    "{{ $json.name }}"          -> item["json"]["name"]
    "Hello {{ $json.user }}!"   -> "Hello alice!"
    "{{ $json.count }}"         -> returns the actual int/float, not a string
                                   (if the whole value is a single expression)
"""

from __future__ import annotations
import re
from typing import Any

EXPR_RE = re.compile(r"\{\{\s*(.*?)\s*\}\}")


def resolve_expr(value: Any, item_json: dict) -> Any:
    """Interpolate {{ $json.field }} expressions in a param value."""
    if not isinstance(value, str):
        return value
    matches = EXPR_RE.findall(value)
    if not matches:
        return value
    # If the entire string is one expression, return the raw value (preserves types)
    if EXPR_RE.fullmatch(value.strip()):
        expr = matches[0].strip()
        return _eval_expr(expr, item_json)
    # Otherwise do string interpolation
    def replacer(m):
        result = _eval_expr(m.group(1).strip(), item_json)
        return str(result) if result is not None else ""
    return EXPR_RE.sub(replacer, value)


def _eval_expr(expr: str, item_json: dict) -> Any:
    """Evaluate a single expression like '$json.field.subfield'"""
    if expr.startswith("$json"):
        rest = expr[5:]  # strip "$json"
        val = item_json
        if rest:
            for part in rest.lstrip(".").split("."):
                if isinstance(val, dict):
                    val = val.get(part)
                elif isinstance(val, list):
                    try:
                        val = val[int(part)]
                    except (ValueError, IndexError):
                        val = None
                else:
                    val = None
                if val is None:
                    break
        return val
    # fallback: try eval in a safe scope
    try:
        return eval(expr, {"__builtins__": {}}, {"json": item_json})
    except Exception:
        return expr


def make_item(data: dict | None = None) -> dict:
    """Helper: wrap a plain dict into the standard item shape."""
    return {"json": data or {}}


class Node:
    TYPE: str = "base"
    TITLE: str = "Base Node"
    CATEGORY: str = "core"
    INPUTS: int = 1
    OUTPUTS: int = 1
    PARAMS: list[dict] = []

    def __init__(self, name: str, params: dict | None = None):
        self.name = name
        self.params = params or {}

    def rexpr(self, value: Any, item_json: dict) -> Any:
        return resolve_expr(value, item_json)

    def resolve(self, key: str, item_json: dict, default: Any = None) -> Any:
        """Get a param value with {{ }} expressions resolved against item_json."""
        val = self.params.get(key, default)
        return resolve_expr(val, item_json)

    def p(self, key: str, default: Any = None) -> Any:
        """Shorthand for reading a raw param value (no expression resolving)."""
        val = self.params.get(key, default)
        return default if val is None else val

    def run(self, items: list[dict]) -> list[dict] | list[list[dict]]:
        raise NotImplementedError(f"Node {self.TYPE} has no run() implemented")

    def __repr__(self):
        return f"<{self.TYPE} '{self.name}'>"
