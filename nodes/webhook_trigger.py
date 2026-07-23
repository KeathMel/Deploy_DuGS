"""
Webhook Trigger: starts a workflow when an HTTP request hits a given path.

This node does NOT run like a normal node — the API server reads its params
at registration time to know which path/method to listen on. When run() is
called directly (e.g. from the Run button in the UI, with no real request),
it just outputs whatever sample data you give it, so you can still test the
rest of the workflow without firing a real HTTP request.

Params:
  path    — the URL path to listen on, e.g. "/my-hook"
  method  — GET / POST / PUT / DELETE / ANY
  sample  — fake request data used when testing from the editor (Run button)

When a REAL request comes in, the API server builds the item as:
  {
    "json": {
      "method": "POST",
      "path": "/my-hook",
      "query": {...},
      "headers": {...},
      "body": <parsed JSON body, or raw text, or null>
    }
  }
"""
from node_base import Node, make_item


class WebhookTrigger(Node):
    TYPE = "webhook.trigger"
    TITLE = "Webhook"
    CATEGORY = "trigger"
    INPUTS = 0
    OUTPUTS = 1
    PARAMS = [
        {"key": "path", "label": "Path (e.g. /my-hook)", "type": "text", "default": "/webhook"},
        {
            "key": "method",
            "label": "Method",
            "type": "select",
            "default": "POST",
            "options": ["ANY", "GET", "POST", "PUT", "PATCH", "DELETE"],
        },
        {
            "key": "sample",
            "label": "Sample data (used when testing in editor)",
            "type": "json",
            "default": {"method": "POST", "path": "/webhook", "query": {}, "headers": {}, "body": {"example": True}},
        },
    ]

    def run(self, items):
        # If the engine was started at this node with real webhook request data
        # (via start_node/start_data in api.py), `items` will contain it —
        # use that. Otherwise (e.g. testing from the editor's Run button with
        # no real request), fall back to the sample data.
        if items:
            return items
        sample = self.params.get("sample") or {}
        return [make_item(sample)]
