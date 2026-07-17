"""
Tabel node: read from, append to, or update rows in a Tabel spreadsheet.

Operations:
  read    — outputs every row as an item
  append  — takes incoming items, appends them as new rows, outputs the new rows
  update  — takes incoming items (must have an 'id' field), updates matching rows
  delete  — takes incoming items with 'id', deletes those rows, outputs deleted rows
  clear   — removes all rows, outputs nothing
"""
import os
import sys
from node_base import Node, resolve_expr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tabel_store


class TabelNode(Node):
    TYPE = "data.tabel"
    TITLE = "Tabel"
    CATEGORY = "data"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "tabel", "label": "Tabel", "type": "tabel", "default": ""},
        {
            "key": "operation",
            "label": "Operation",
            "type": "select",
            "default": "read",
            "options": ["read", "append", "update", "delete", "clear"],
        },
        {
            "key": "filter_field",
            "label": "Filter field (for read, optional)",
            "type": "text",
            "default": "",
        },
        {
            "key": "filter_value",
            "label": "Filter value (or {{ $json.x }})",
            "type": "text",
            "default": "",
        },
    ]

    def run(self, items):
        name = self.params.get("tabel")
        if not name:
            raise ValueError("Tabel node needs a tabel name")

        op = (self.params.get("operation") or "read").lower()

        try:
            data = tabel_store.load_tabel(name)
        except FileNotFoundError:
            raise ValueError(f"Tabel '{name}' does not exist — create it in the Tabels tab first")

        cols = data.get("columns", [])
        rows = data.get("rows", [])

        if op == "read":
            filter_field = (self.params.get("filter_field") or "").strip()
            filter_value = self.params.get("filter_value", "")
            # resolve filter_value against first incoming item if available
            if items and filter_value:
                filter_value = resolve_expr(str(filter_value), items[0].get("json", {}))
            if filter_field and filter_value != "":
                rows = [r for r in rows if str(r.get(filter_field, "")) == str(filter_value)]
            return [{"json": dict(r)} for r in rows]

        if op == "append":
            added = []
            for it in (items or []):
                j = it.get("json", {})
                row = {c: j.get(c) for c in cols}
                rows.append(row)
                added.append(row)
            data["rows"] = rows
            tabel_store.save_tabel(name, data)
            # reload to get auto-assigned ids
            data = tabel_store.load_tabel(name)
            saved_rows = data["rows"][-len(added):] if added else []
            return [{"json": dict(r)} for r in saved_rows]

        if op == "update":
            updated = []
            by_id = {r.get("id"): r for r in rows}
            for it in (items or []):
                j = it.get("json", {})
                rid = j.get("id")
                if rid in by_id:
                    for c in cols:
                        if c in j:
                            by_id[rid][c] = j[c]
                    updated.append({"json": dict(by_id[rid])})
            data["rows"] = rows
            tabel_store.save_tabel(name, data)
            return updated

        if op == "delete":
            to_delete = {it.get("json", {}).get("id") for it in (items or [])}
            deleted = [r for r in rows if r.get("id") in to_delete]
            data["rows"] = [r for r in rows if r.get("id") not in to_delete]
            tabel_store.save_tabel(name, data)
            return [{"json": dict(r)} for r in deleted]

        if op == "clear":
            data["rows"] = []
            tabel_store.save_tabel(name, data)
            return []

        raise ValueError(f"Unknown Tabel operation: {op}")
