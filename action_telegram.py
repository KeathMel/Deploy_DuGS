"""
Telegram — send a message to a Telegram chat via a bot.

Setup (one time):
  1. Talk to @BotFather on Telegram, create a bot, copy its TOKEN.
  2. Get your chat id (message the bot, then check
     https://api.telegram.org/bot<TOKEN>/getUpdates, or use @userinfobot).

Then this node POSTs to Telegram's sendMessage API. Great for "ping my phone
when X happens."

SETTINGS
========
token    : the bot token (or leave blank and use a saved Credential)
chat_id  : who to send to
text     : the message ({{ }} allowed)
"""
import json
import urllib.request
from node_base import Node


class TelegramNode(Node):
    TYPE = "action.telegram"
    TITLE = "Telegram"
    CATEGORY = "action"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "credential", "label": "Credential (saved bot token)", "type": "select",
         "default": "", "options_from": "credentials"},
        {"key": "token", "label": "or paste Bot Token", "type": "text", "default": ""},
        {"key": "chat_id", "label": "Chat ID", "type": "text", "default": ""},
        {"key": "text", "label": "Message ({{ }} allowed)", "type": "multiline",
         "default": "{{ $json.message }}"},
    ]

    def _token(self):
        cred = (self.params.get("credential") or "").strip()
        if cred:
            try:
                from storage import load_credential
                d = load_credential(cred)
                t = (d.get("token") or d.get("api_key") or "").strip()
                if t:
                    return t
            except Exception:
                pass
        return (self.params.get("token") or "").strip()

    def run(self, items):
        token = self._token()
        chat_id = (self.params.get("chat_id") or "").strip()
        tpl = self.params.get("text", "") or ""
        if not token or not chat_id:
            return [{"json": {"error": "Telegram: token and chat_id are required"}}]
        out = []
        for it in items:
            j = dict(it.get("json", {}))
            text = self.rexpr(tpl, j) if "{{" in tpl else tpl
            if not isinstance(text, str):
                text = json.dumps(text)
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
                req = urllib.request.Request(url, data=data,
                                             headers={"Content-Type": "application/json"},
                                             method="POST")
                with urllib.request.urlopen(req, timeout=15) as r:
                    resp = json.loads(r.read().decode("utf-8"))
                j["telegram_ok"] = bool(resp.get("ok"))
            except Exception as e:
                j["telegram_ok"] = False
                j["telegram_error"] = str(e)
            out.append({"json": j})
        return out
