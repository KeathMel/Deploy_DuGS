"""
ai_helper.py — a tiny OpenAI-compatible chat client plus a cumulative token
counter, shared by any node that talks to an AI.

Works with any provider that speaks the OpenAI /chat/completions shape
(OpenAI, DeepSeek, Together, local servers, ...) — you just point base_url at
the right place and give it a key.

The token counter is process-wide and adds up every completion's usage, so a
node can check "have we used more than N tokens this run" and the Run Log can
show the running total.
"""
import json
import urllib.request

# cumulative tokens used since the process started (or since last reset)
_TOKENS_USED = 0


def tokens_used():
    return _TOKENS_USED


def reset_tokens():
    global _TOKENS_USED
    _TOKENS_USED = 0


def _add_tokens(n):
    global _TOKENS_USED
    _TOKENS_USED += int(n or 0)


def chat(api_key, prompt, system="", model="gpt-4o-mini",
         base_url="https://api.openai.com/v1", temperature=0.3, timeout=60,
         max_tokens=None):
    """One chat completion. Returns (text, tokens_used_this_call).

    max_tokens, if given, caps the length of this single reply.
    Raises on network/HTTP errors so the caller can surface them.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = int(max_tokens)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    text = data["choices"][0]["message"]["content"]
    used = (data.get("usage") or {}).get("total_tokens", 0)
    _add_tokens(used)
    return text, used
