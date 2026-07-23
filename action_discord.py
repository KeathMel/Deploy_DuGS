"""
Discord — post a message to a Discord channel via a webhook.

Setup (one time):
  In Discord: Channel settings -> Integrations -> Webhooks -> New Webhook ->
  Copy Webhook URL. That URL is all you need — no bot, no OAuth.

Then this node POSTs your message to that webhook.

SETTINGS
========
webhook_url : the Discord webhook URL (or a saved Credential holding it)
text        : the message ({{ }} allowed)
username    : optional display name to post as
"""
import json
import urllib.request
from node_base import Node


class DiscordNode(Node):
    TYPE = "action.discord"
    TITLE = "Discord"
    CATEGORY = "action"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "credential", "label": "Credential (saved webhook URL)", "type": "select",
         "default": "", "options_from": "credentials"},
        {"key": "webhook_url", "label": "or paste Webhook URL", "type": "text", "default": ""},
        {"key": "text", "label": "Message ({{ }} allowed)", "type": "multiline",
         "default": "{{ $json.message }}"},
        {"key": "username", "label": "Post as (optional)", "type": "text", "default": ""},
    ]

    def _url(self):
        cred = (self.params.get("credential") or "").strip()
        if cred:
            try:
                from storage import load_credential
                d = load_credential(cred)
                u = (d.get("token") or d.get("url") or d.get("api_key") or "").strip()
                if u:
                    return u
            except Exception:
                pass
        return (self.params.get("webhook_url") or "").strip()

    def run(self, items):
        url = self._url()
        tpl = self.params.get("text", "") or ""
        username = (self.params.get("username") or "").strip()
        if not url:
            return [{"json": {"error": "Discord: webhook_url is required"}}]
        out = []
        for it in items:
            j = dict(it.get("json", {}))
            text = self.rexpr(tpl, j) if "{{" in tpl else tpl
            if not isinstance(text, str):
                text = json.dumps(text)
            payload = {"content": text}
            if username:
                payload["username"] = username
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data,
                                             headers={"Content-Type": "application/json"},
                                             method="POST")
                with urllib.request.urlopen(req, timeout=15) as r:
                    code = r.getcode()
                j["discord_ok"] = code in (200, 204)
            except Exception as e:
                j["discord_ok"] = False
                j["discord_error"] = str(e)
            out.append({"json": j})
        return out
