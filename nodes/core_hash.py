"""
Hash — hash or HMAC-sign a value.

mode = "hash"
    plain hash of a field's value (md5 / sha1 / sha256).
mode = "hmac"
    keyed HMAC signature (sha256), for signing webhook payloads or verifying
    them. Needs a secret key.

    field  : which field to hash (supports {{ }})
    algo   : md5 / sha1 / sha256
    key    : secret (hmac mode only)
    into   : where to store the hex digest
"""
import hashlib
import hmac as _hmac
from node_base import Node


class HashNode(Node):
    TYPE = "core.hash"
    TITLE = "Hash"
    CATEGORY = "core"
    INPUTS = 1
    OUTPUTS = 1
    PARAMS = [
        {"key": "mode", "label": "Mode", "type": "select", "default": "hash",
         "options": ["hash", "hmac"]},
        {"key": "field", "label": "Field to hash ({{ }} allowed)", "type": "text", "default": "data"},
        {"key": "algo", "label": "Algorithm", "type": "select", "default": "sha256",
         "options": ["md5", "sha1", "sha256"]},
        {"key": "key", "label": "Secret key (hmac mode)", "type": "text", "default": ""},
        {"key": "into", "label": "Store digest in field", "type": "text", "default": "hash"},
    ]

    def run(self, items):
        mode = self.params.get("mode", "hash")
        field = (self.params.get("field") or "data").strip()
        algo = self.params.get("algo", "sha256")
        key = self.params.get("key", "") or ""
        into = (self.params.get("into") or "hash").strip()
        out = []
        for it in items:
            j = dict(it.get("json", {}))
            raw = self.rexpr("{{ $json." + field + " }}", j) if "{{" not in field else self.rexpr(field, j)
            msg = (raw if isinstance(raw, str) else str(raw)).encode("utf-8")
            try:
                if mode == "hmac":
                    digest = _hmac.new(key.encode("utf-8"), msg, algo).hexdigest()
                else:
                    digest = hashlib.new(algo, msg).hexdigest()
            except Exception as e:
                digest = f"error: {e}"
            j[into] = digest
            out.append({"json": j})
        return out
