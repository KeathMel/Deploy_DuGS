"""
Respond to Webhook: sends an HTTP response back to whoever triggered the
workflow via a Webhook Trigger node, then the workflow stops.

If a workflow has a Webhook Trigger but NO Respond node, the API server
auto-responds with {"ok": true} once the workflow finishes.

If you test this from the editor's Run button (not a real HTTP hit), it just
passes the data through — there's no real request to respond to.

Params:
  status        — HTTP status code to send back
  body_mode     — "pass through item" (send the incoming item's json as-is)
                  or "custom" (build a specific JSON body, expressions allowed)
  custom_body   — JSON used when body_mode is "custom". Supports {{ $json.x }}
"""
from node_base import Node, resolve_expr


class WebhookRespondSignal(Exception):
    """Raised to bubble the response payload up to whatever is running the
    engine (api.py's webhook handler). Caught there; ignored harmlessly if
    the workflow was run normally (e.g. from the editor's Run button)."""
    def __init__(self, status, body):
        self.status = status
        self.body = body
        super().__init__(f"webhook respond: {status}")


class WebhookRespond(Node):
    TYPE = "webhook.respond"
    TITLE = "Respond to Webhook"
    CATEGORY = "action"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "status", "label": "Status code", "type": "number", "default": 200},
        {
            "key": "body_mode",
            "label": "Body",
            "type": "select",
            "default": "pass through item",
            "options": ["pass through item", "custom"],
        },
        {
            "key": "custom_body",
            "label": "Custom body (JSON, {{ $json.x }} allowed)",
            "type": "json",
            "default": {"ok": True},
        },
        {
            "key": "is_test_run",
            "label": "(internal) treat as real webhook response",
            "type": "bool",
            "default": False,
        },
    ]

    def run(self, items):
        status = int(self.params.get("status", 200) or 200)
        mode = self.params.get("body_mode", "pass through item")
        item = items[0] if items else {"json": {}}
        j = item.get("json", {})

        if mode == "custom":
            raw = self.params.get("custom_body", {})
            body = self._resolve_deep(raw, j)
        else:
            body = j

        # If the API server flagged this as a real webhook execution, raise
        # the signal so api.py can catch it and actually write the HTTP
        # response. Otherwise (editor test run) just pass data through.
        if self.params.get("is_test_run"):
            raise WebhookRespondSignal(status, body)

        return [{"json": body}]

    def _resolve_deep(self, val, j):
        if isinstance(val, str):
            return resolve_expr(val, j)
        if isinstance(val, dict):
            return {k: self._resolve_deep(v, j) for k, v in val.items()}
        if isinstance(val, list):
            return [self._resolve_deep(v, j) for v in val]
        return val
