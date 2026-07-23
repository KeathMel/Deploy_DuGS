"""
Notes — A scratchpad node for leaving documentation, notes, or raw text inside a workflow.

SETTINGS
========
text : the notes content written down inside the node.
"""
from node_base import Node


class NotesNode(Node):
    TYPE = "utility.notes"
    TITLE = "Notes"
    CATEGORY = "utility"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {
            "key": "text",
            "label": "Notes",
            "type": "multiline",
            "default": "Type your notes here...",
        }
    ]

    def get_tooltip(self):
        """Returns the notes preview text when hovering over the node in the UI."""
        notes_text = (self.params.get("text") or "").strip()
        if not notes_text:
            return "No notes added."
        return notes_text[:200] + ("..." if len(notes_text) > 200 else "")

    def run(self, items):
        notes_text = self.params.get("text", "") or ""

        if not items:
            return [{"json": {"notes": notes_text}}]

        out = []
        for it in items:
            j = dict(it.get("json", {}))
            j["notes"] = notes_text
            out.append({"json": j})

        return out
