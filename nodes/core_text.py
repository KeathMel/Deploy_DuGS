"""
Text Template — build a string from fields, using {{ }} expressions.

Write a template with placeholders and it fills them in per item:

    "Hi {{ $json.name }}, your order {{ $json.id }} shipped."

The filled string is stored in a field you choose. Great for building email
bodies, chat messages, log lines, etc.

SETTINGS
========
template : the text, with {{ }} references
into     : field to store the result in
"""
from node_base import Node


class TextTemplateNode(Node):
    TYPE = "core.text"
    TITLE = "Text Template"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "template", "label": "Template ({{ }} allowed)", "type": "multiline",
         "default": "Hello {{ $json.name }}"},
        {"key": "into", "label": "Store result in field", "type": "text", "default": "text"},
    ]

    def run(self, items):
        tpl = self.params.get("template", "") or ""
        into = (self.params.get("into") or "text").strip()
        out = []
        for it in items:
            j = dict(it.get("json", {}))
            j[into] = self.rexpr(tpl, j) if "{{" in tpl else tpl
            out.append({"json": j})
        return out
