"""
Edit Fields — rename, remove, or keep-only fields on each item.

Your Set node ADDS fields; this one cleans up:

    rename : "old:new, foo:bar"   ->  renames old->new and foo->bar
    remove : "temp, debug"         ->  deletes those fields
    keep   : "id, name"            ->  drops everything EXCEPT these
                                        (leave blank to keep all)

Applied in order: rename, then remove, then keep.
"""
from node_base import Node


class EditFieldsNode(Node):
    TYPE = "core.edit_fields"
    TITLE = "Edit Fields"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "rename", "label": "Rename (old:new, comma separated)", "type": "text", "default": ""},
        {"key": "remove", "label": "Remove (comma separated)", "type": "text", "default": ""},
        {"key": "keep", "label": "Keep only (comma separated, blank = all)", "type": "text", "default": ""},
    ]

    def _pairs(self, raw):
        out = []
        for part in str(raw or "").split(","):
            part = part.strip()
            if ":" in part:
                a, b = part.split(":", 1)
                out.append((a.strip(), b.strip()))
        return out

    def _list(self, raw):
        return [p.strip() for p in str(raw or "").split(",") if p.strip()]

    def run(self, items):
        renames = self._pairs(self.params.get("rename"))
        removes = self._list(self.params.get("remove"))
        keeps = self._list(self.params.get("keep"))
        out = []
        for it in items:
            j = dict(it.get("json", {}))
            for old, new in renames:
                if old in j:
                    j[new] = j.pop(old)
            for r in removes:
                j.pop(r, None)
            if keeps:
                j = {k: v for k, v in j.items() if k in keeps}
            out.append({"json": j})
        return out
