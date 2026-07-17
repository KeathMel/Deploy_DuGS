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
# matches  $('Node Name').item.json.rest...   OR  $("Node Name")...
NODE_REF_RE = re.compile(r"""\$\(\s*['"](.+?)['"]\s*\)(.*)""")


def resolve_expr(value: Any, item_json: dict, context: dict | None = None) -> Any:
    """Interpolate {{ ... }} expressions in a param value.

    Supports two reference styles:
      {{ $json.field.sub }}                      -> the current item's data
      {{ $('Node Name').item.json.field }}       -> another node's output
    `context` maps node name -> that node's output items (list of {"json":...})
    so cross-node references can be resolved.
    """
    if not isinstance(value, str):
        return value
    matches = EXPR_RE.findall(value)
    if not matches:
        return value
    if EXPR_RE.fullmatch(value.strip()):
        expr = matches[0].strip()
        return _eval_expr(expr, item_json, context)
    def replacer(m):
        result = _eval_expr(m.group(1).strip(), item_json, context)
        return str(result) if result is not None else ""
    return EXPR_RE.sub(replacer, value)


def _walk_path(val, path: str):
    """Follow a dotted/indexed path like '.body.message' or '[0].name'."""
    # normalise [n] into .n
    path = re.sub(r"\[(\d+)\]", r".\1", path)
    for part in path.lstrip(".").split("."):
        if part == "":
            continue
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


def _eval_expr(expr: str, item_json: dict, context: dict | None = None) -> Any:
    """Evaluate a single expression."""
    expr = expr.strip()

    # ---- cross-node reference: $('Node Name').item.json.path ----
    m = NODE_REF_RE.match(expr)
    if m:
        node_name = m.group(1)
        rest = m.group(2)  # e.g.  .item.json.body.message
        items = (context or {}).get(node_name)
        if not items:
            return None
        # take the first item by default (n8n's .item)
        first = items[0] if isinstance(items, list) and items else {}
        # strip a leading ".item" if present
        rest = re.sub(r"^\s*\.item\b", "", rest)
        # strip a leading ".json" -> we index into the item's json
        target = first.get("json", first) if isinstance(first, dict) else first
        rest = re.sub(r"^\s*\.json\b", "", rest)
        return _walk_path(target, rest)

    # ---- current item: $json.path ----
    if expr.startswith("$json"):
        return _walk_path(item_json, expr[5:])

    # fallback: safe eval with both $json and a node accessor
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
        self._context: dict | None = None   # set by the engine before run()

    def rexpr(self, value: Any, item_json: dict) -> Any:
        """Resolve {{ }} in `value`, with access to other nodes' outputs."""
        return resolve_expr(value, item_json, getattr(self, "_context", None))

    def resolve(self, key: str, item_json: dict, default: Any = None) -> Any:
        """Get a param value with {{ }} expressions resolved against item_json."""
        val = self.params.get(key, default)
        return resolve_expr(val, item_json, getattr(self, "_context", None))

    def run(self, items: list[dict]) -> list[dict] | list[list[dict]]:
        raise NotImplementedError(f"Node {self.TYPE} has no run() implemented")

    def __repr__(self):
        return f"<{self.TYPE} '{self.name}'>"
