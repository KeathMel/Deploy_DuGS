"""
AI node — sends a prompt to DeepSeek and puts the reply back on the item.

Pure stdlib (urllib), no installs needed. You supply your own DeepSeek API
token in the node settings; nothing else to configure.

DeepSeek uses the OpenAI chat-completions wire format:
    POST https://api.deepseek.com/chat/completions
    Authorization: Bearer <token>
    { "model": ..., "messages": [...] }
Reply text is at  choices[0].message.content.

SETTINGS
========
api_key       : your DeepSeek token (from platform.deepseek.com).
model         : which DeepSeek model (dropdown).
system_prompt : optional. Sets the assistant's role/behaviour.
user_prompt   : the message sent to the model. Supports {{ }} references like
                every other field, e.g.  Summarise: {{ $json.body.message }}
output_shape  : optional. Paste a JSON example, e.g.
                    { "reply": "your reply goes here" }
                and the node forces the model to return JSON in exactly that
                shape, then merges the parsed object onto the item. DeepSeek
                has a native JSON mode (response_format) which we switch on
                automatically when a shape is given. Blank -> the raw text
                reply is written to the `reply` field.
max_tokens    : response length cap.

OUTPUT SHAPE ENFORCEMENT
========================
When output_shape is set we (a) flip on DeepSeek's response_format json_object
mode, and (b) append a hidden system instruction telling the model to reply
with ONLY a JSON object matching those keys. The reply is JSON-parsed (with
markdown-fence stripping as a fallback).
"""
import json
import urllib.request
import urllib.error
from node_base import Node, resolve_expr

# Official DeepSeek OpenAI-compatible endpoint.
API_URL = "https://api.deepseek.com/chat/completions"


class AINode(Node):
    TYPE = "ai.agent"
    TITLE = "AI"
    CATEGORY = "ai"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "credential", "label": "Credential (saved token)", "type": "select",
         "default": "", "options_from": "credentials"},
        {"key": "api_key", "label": "or paste DeepSeek Token", "type": "text", "default": ""},
        {"key": "model", "label": "Model", "type": "select",
         "default": "deepseek-v4-flash",
         "options": [
             "deepseek-v4-flash",   # fast / cheap
             "deepseek-v4-pro",     # higher capability
             "deepseek-chat",       # legacy alias (non-thinking)
             "deepseek-reasoner",   # legacy alias (thinking)
         ]},
        {"key": "input", "label": "Input (supports {{ }})", "type": "multiline",
         "default": "{{ $json }}"},
        {"key": "system_prompt", "label": "System prompt (optional)", "type": "multiline", "default": ""},
        {"key": "output_shape", "label": "Output JSON example (optional)", "type": "multiline",
         "default": ""},
        {"key": "max_tokens", "label": "Max tokens", "type": "number", "default": 1024},
    ]

    def _resolve_key(self):
        """Prefer a saved credential; fall back to a pasted token. If the
        'credential' field itself contains a raw token (starts with sk-),
        use it directly so a mis-paste still works."""
        cred = (self.params.get("credential") or "").strip()
        if cred:
            # a raw token pasted into the credential box
            if cred.startswith("sk-") or len(cred) > 40:
                return cred
            try:
                from storage import load_credential
                data = load_credential(cred)
                tok = (data.get("token") or data.get("api_key") or "").strip()
                if tok:
                    return tok
            except Exception:
                pass
        return (self.params.get("api_key") or "").strip()

    def run(self, items):
        api_key = self._resolve_key()
        model = self.params.get("model", "deepseek-v4-flash")
        system_prompt = self.params.get("system_prompt", "") or ""
        input_tpl = self.params.get("input", "") or ""
        shape_raw = (self.params.get("output_shape") or "").strip()
        try:
            max_tokens = int(self.params.get("max_tokens", 1024) or 1024)
        except (TypeError, ValueError):
            max_tokens = 1024

        if not api_key:
            return [{"json": {"error": "AI node: no DeepSeek token set"}}]

        shape_obj = None
        if shape_raw:
            try:
                shape_obj = json.loads(shape_raw)
            except json.JSONDecodeError as e:
                return [{"json": {"error": f"AI node: output shape is not valid JSON ({e})"}}]

        out = []
        for item in items:
            j = item.get("json", {})

            # resolve {{ }} references against this item (and other nodes)
            user_msg = self.rexpr(input_tpl, j) if input_tpl else ""
            if not isinstance(user_msg, str):
                user_msg = json.dumps(user_msg)
            sys_msg = self.rexpr(system_prompt, j) if system_prompt else ""
            if not isinstance(sys_msg, str):
                sys_msg = json.dumps(sys_msg)
            # only ever send non-empty content; blanks must not reach the model
            user_msg = user_msg.strip()
            sys_msg = sys_msg.strip()

            if shape_obj is not None:
                shape_str = json.dumps(shape_obj, indent=2)
                enforce = (
                    "You must respond with ONLY a single valid JSON object that "
                    "matches exactly this shape (same keys), and nothing else — "
                    "no explanation, no markdown code fences:\n" + shape_str
                )
                sys_msg = (sys_msg + "\n\n" + enforce).strip() if sys_msg else enforce

            # build OpenAI-format messages. Only include a system message if
            # there's actually system content. The user message must be
            # non-empty (the API requires at least one message) — if the input
            # resolved to nothing, skip this item with a clear note.
            if not user_msg:
                out.append({"json": {**j, "error": "AI node: input is empty, nothing sent"}})
                continue

            messages = []
            if sys_msg:
                messages.append({"role": "system", "content": sys_msg})
            messages.append({"role": "user", "content": user_msg})

            body = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": messages,
                "stream": False,
            }
            # DeepSeek native JSON mode when a shape is requested
            if shape_obj is not None:
                body["response_format"] = {"type": "json_object"}

            try:
                reply_text = self._call(api_key, body)
            except Exception as e:
                out.append({"json": {**j, "error": f"AI node request failed: {e}"}})
                continue

            if shape_obj is not None:
                parsed = self._parse_json(reply_text)
                if parsed is None:
                    out.append({"json": {**j, "error": "AI node: reply was not valid JSON",
                                          "raw_reply": reply_text}})
                else:
                    out.append({"json": {**j, **parsed}})
            else:
                out.append({"json": {**j, "reply": reply_text}})

        return out

    def _call(self, api_key, body):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            API_URL, data=data, method="POST",
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")
            raise RuntimeError(f"HTTP {e.code}: {detail[:300]}")
        # OpenAI-format response: choices[0].message.content
        choices = payload.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            return (msg.get("content") or "").strip()
        return ""

    def _parse_json(self, text):
        if not text:
            return None
        t = text.strip()
        if t.startswith("```"):
            parts = t.split("```")
            t = parts[1] if len(parts) > 1 else text
            if t.startswith("json"):
                t = t[4:]
            t = t.strip().rstrip("`").strip()
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            start = t.find("{"); end = t.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(t[start:end + 1])
                except json.JSONDecodeError:
                    return None
            return None
