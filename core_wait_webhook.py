"""
Wait for Webhook — pause the whole workflow until an HTTP call wakes it up.

Unlike the Delay/Wait node (which just sleeps a fixed number of seconds), this
node suspends the run INDEFINITELY. The workflow stops here and the engine saves
its half-finished state to disk with a resume id. Nothing runs, nothing blocks.

When an HTTP call hits the matching resume URL:

    POST /resume/<id>   { ...any json... }

the run picks up right where it left off, and the data from that call flows out
of this node into whatever comes next.

Use it for: wait-for-approval, wait-for-a-user-to-click, wait-for-an-external
system to call back, human-in-the-loop steps.

The node raises WaitSignal, which the engine catches (exactly like the webhook
respond node raises WebhookRespondSignal to end a run early).
"""
from node_base import Node


class WaitSignal(Exception):
    """Raised to suspend a run until an external resume call arrives."""
    def __init__(self, node_name, label=""):
        super().__init__(f"waiting at {node_name}")
        self.node_name = node_name
        self.label = label


class WaitForWebhookNode(Node):
    TYPE = "core.wait_webhook"
    TITLE = "Wait for Webhook"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "label", "label": "Label (shown while waiting)", "type": "text",
         "default": "waiting for callback"},
    ]

    def run(self, items):
        # suspend here — the engine catches this and freezes the run
        raise WaitSignal(self.name, self.params.get("label", ""))
