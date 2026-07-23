"""
Memory Write — save a value into a Memory Bank, with optional AI compaction.

A Memory Bank is DuGS's simple key/value store (make one on the home screen,
next to Tabels). This node writes a value under a key. You can give it a time
limit so the entry expires on its own, and you can choose to append to what is
already there instead of overwriting.

AI COMPACTION (the switch)
==========================
Turn "Compact with AI" on and extra options appear. When the AI has used more
than your token threshold this run (shown in the Run Log), the stored text is
sent to the AI along with your instructions, and whatever it returns takes the
place of — or is added to — the entry. Use it to keep a growing memory from
blowing up: every so often the AI boils it down to the important bits.

SETTINGS
========
bank        : which memory bank to write to
key         : the key to store under; {{ }} allowed
value       : what to store; {{ }} allowed
ttl_minutes : minutes until it expires (0 = never)
append      : add to the existing value instead of replacing it

compact         : master switch for AI compaction
credential      : saved AI credential (api key, and optional base url / model)
token_threshold : compact once the run has used more than this many AI tokens
system_prompt   : how the AI should compact — your instructions
compact_mode    : replace the entry with the summary, or append the summary
"""
import os
import sys

from node_base import Node

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import storage
import ai_helper


class MemoryWriteNode(Node):
    TYPE = "memory.write"
    TITLE = "Memory Write"
    CATEGORY = "data"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "bank", "label": "Memory Bank", "type": "memory", "default": "",
         "desc": "Which memory bank to write to."},
        {"key": "key", "label": "Key", "type": "text", "default": "",
         "desc": "The key to store the value under.", "example": "chat_history"},
        {"key": "value", "label": "Value", "type": "multiline", "default": "",
         "desc": "What to store. Expressions allowed.",
         "example": "{{ $json.message }}"},
        {"key": "ttl_minutes", "label": "Expire after (minutes)", "type": "number",
         "default": 0,
         "desc": "How long the entry lives. 0 means it never expires."},
        {"key": "append", "label": "Append instead of replace", "type": "bool",
         "default": False,
         "desc": "Add to the existing value rather than overwriting it."},

        # ---- AI compaction ----
        {"key": "compact", "label": "Compact with AI", "type": "bool",
         "default": False,
         "desc": "When on, the stored text is periodically summarised by the AI "
                 "so a growing memory stays small."},
        {"key": "credential", "label": "AI credential", "type": "select",
         "default": "", "options_from": "credentials",
         "desc": "A saved credential holding the AI api key (and optional "
                 "base_url / model).",
         "show_if": {"compact": True}},
        {"key": "token_threshold", "label": "Compact after N tokens",
         "type": "number", "default": 2000,
         "desc": "Once the run has used more than this many AI tokens, the "
                 "entry gets compacted on write.",
         "show_if": {"compact": True}},
        {"key": "system_prompt", "label": "Compaction instructions",
         "type": "multiline",
         "default": "Summarise the following, keeping only the important facts. "
                    "Be concise.",
         "desc": "How the AI should compact the stored text.",
         "show_if": {"compact": True}},
        {"key": "compact_mode", "label": "Result", "type": "select",
         "default": "replace", "options": ["replace", "append"],
         "desc": "Replace the entry with the summary, or append the summary.",
         "show_if": {"compact": True}},
    ]

    # ---- helpers -----------------------------------------------------------
    def _credential(self):
        """Pull api_key / base_url / model out of the saved credential."""
        name = self.p("credential", "")
        if not name:
            return None
        try:
            d = storage.load_credential(name) or {}
        except Exception:
            return None
        key = (d.get("api_key") or d.get("token") or d.get("key") or "").strip()
        if not key:
            return None
        return {
            "api_key": key,
            "base_url": d.get("base_url") or "https://api.openai.com/v1",
            "model": d.get("model") or "gpt-4o-mini",
        }

    def _maybe_compact(self, current_text):
        """If compaction is on and the token threshold is passed, run the AI
        over current_text and return (new_text, note). Otherwise return
        (current_text, None)."""
        if not self.p("compact", False):
            return current_text, None
        threshold = int(self.p("token_threshold", 2000) or 0)
        used = ai_helper.tokens_used()
        if used <= threshold:
            return current_text, None    # not time yet
        cred = self._credential()
        if cred is None:
            return current_text, "compact skipped: no valid AI credential"
        try:
            summary, spent = ai_helper.chat(
                cred["api_key"],
                prompt=str(current_text),
                system=self.p("system_prompt", ""),
                model=cred["model"],
                base_url=cred["base_url"],
            )
        except Exception as e:
            return current_text, f"compact failed: {e}"
        if self.p("compact_mode", "replace") == "append":
            return f"{current_text}\n\n[AI summary]\n{summary}", \
                   f"compacted (+{spent} tokens, appended)"
        return summary, f"compacted (+{spent} tokens, replaced)"

    # ---- run ---------------------------------------------------------------
    def run(self, items):
        bank = self.p("bank")
        if not bank:
            return items or [{"json": {}}]
        ttl = int(self.p("ttl_minutes", 0) or 0)
        ttl_seconds = ttl * 60 if ttl > 0 else None
        append = bool(self.p("append", False))

        out = []
        for it in (items or [{"json": {}}]):
            j = it.get("json", {})
            key = self.rexpr(self.p("key", ""), j)
            value = self.rexpr(self.p("value", ""), j)

            # write first, so what's stored is what we then compact
            stored = storage.memory_set(bank, key, value,
                                        ttl_seconds=ttl_seconds, append=append)

            # then maybe compact the (possibly appended) result
            new_val, note = self._maybe_compact(stored)
            if note and new_val != stored:
                storage.memory_set(bank, key, new_val, ttl_seconds=ttl_seconds,
                                   append=False)
                stored = new_val

            result = dict(j)
            result["memory_key"] = key
            result["memory_value"] = stored
            result["tokens_used"] = ai_helper.tokens_used()
            if note:
                result["compaction"] = note
            out.append({"json": result})
        return out
