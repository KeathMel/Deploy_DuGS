"""
HTTP Request node: call a web API and put the response into the item stream.
Pure stdlib (urllib) — no installs needed.

Supports {{ $json.field }} expressions in URL, headers, and body.

Output per item:
  { "status": 200, "body": <parsed JSON or raw text>, "headers": {...}, "url": "..." }

Options:
  - response_field: if set, puts the body under this key on the EXISTING item
    (useful for enrichment: keep your data, add the API response)
"""
import json
import urllib.request
import urllib.error
from node_base import Node, resolve_expr


class HttpRequestNode(Node):
    TYPE = "web.http"
    TITLE = "HTTP Request"
    CATEGORY = "action"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "url", "label": "URL", "type": "text", "default": "https://"},
        {
            "key": "method",
            "label": "Method",
            "type": "select",
            "default": "GET",
            "options": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
        },
        {"key": "headers", "label": "Headers (JSON)", "type": "json", "default": {}},
        {"key": "body", "label": "Body (JSON)", "type": "json", "default": None},
        {"key": "timeout", "label": "Timeout (s)", "type": "number", "default": 15},
        {
            "key": "response_mode",
            "label": "Response",
            "type": "select",
            "default": "replace item",
            "options": ["replace item", "add to item"],
        },
        {
            "key": "response_field",
            "label": "Add to item under key (if 'add to item')",
            "type": "text",
            "default": "response",
        },
    ]

    def run(self, items):
        method = (self.params.get("method") or "GET").upper()
        timeout = float(self.params.get("timeout") or 15)
        response_mode = self.params.get("response_mode", "replace item")
        response_field = self.params.get("response_field") or "response"

        run_for = items if items else [{"json": {}}]
        out = []

        for item in run_for:
            j = item.get("json", {})

            # resolve expressions against current item
            url = resolve_expr(self.params.get("url", ""), j)
            if not url or url == "https://":
                raise ValueError("HTTP Request node needs a URL")

            raw_headers = self.params.get("headers") or {}
            if isinstance(raw_headers, str):
                try: raw_headers = json.loads(raw_headers)
                except Exception: raw_headers = {}
            headers = {k: str(resolve_expr(v, j)) for k, v in raw_headers.items()}

            body = self.params.get("body")
            data_bytes = None
            if body is not None and method not in ("GET", "HEAD"):
                if isinstance(body, str):
                    body = resolve_expr(body, j)
                    try: body = json.loads(body)
                    except Exception: pass
                data_bytes = json.dumps(body).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")

            req = urllib.request.Request(url, data=data_bytes, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    status = resp.status
                    resp_headers = dict(resp.headers.items())
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", errors="replace")
                status = e.code
                resp_headers = dict(e.headers.items()) if e.headers else {}
            except Exception as e:
                out.append({"json": {"error": str(e), "url": url}})
                continue

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw

            response_data = {"status": status, "body": parsed, "headers": resp_headers, "url": url}

            if response_mode == "add to item":
                new_json = dict(j)
                new_json[response_field] = response_data
                out.append({"json": new_json})
            else:
                out.append({"json": response_data})

        return out
