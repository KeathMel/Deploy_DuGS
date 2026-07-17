"""
api.py — the spine. Wraps the dugs engine in a small HTTP service so anything
(a UI, a container, curl, another machine) can drive it over the network.

Pure Python standard library. No installs.

Endpoints:
  GET  /nodes              -> list available node types (for a UI palette)
  GET  /health             -> {"status": "ok"}
  POST /run                -> body = workflow JSON; runs it; returns per-node results
  POST /webhooks/register  -> body = workflow JSON; scans for webhook.trigger nodes
                               and registers their paths so real HTTP hits route to them
  GET  /webhooks           -> list currently registered webhook routes
  POST /projects/deploy    -> body = workflow JSON (non-servo); saves it into this
                               server's data volume and hot-registers its webhook/
                               schedule triggers. From then on this API runs it on
                               its own, no desktop UI required.
  GET  /schedules          -> list currently registered schedule triggers
  ANY  /hook/<path>        -> a real webhook hit; runs the matching workflow

Run:
  python3 api.py                 # listens on http://127.0.0.1:5800
  python3 api.py 0.0.0.0 5800    # listen on all interfaces (for container/remote)

  Or via environment variables (what the Dockerfile uses):
    DUGS_API_HOST=0.0.0.0 DUGS_API_PORT=5800 DUGS_DATA_DIR=/data python3 api.py
"""

from __future__ import annotations
import os
import sys
import json
import queue
import threading
import time
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from engine import Engine, discover_nodes
from storage import PROJECTS_DIR, save_project

HERE = os.path.dirname(os.path.abspath(__file__))
NODES_DIR = os.path.join(HERE, "nodes")   # node code lives with the app, not the data volume

engine = Engine(NODES_DIR)

# path -> {"workflow": {...}, "node_name": "...", "method": "POST"}
# Registered whenever a workflow containing a webhook.trigger node is saved
# (the UI should POST to /webhooks/register after every save) or on server boot
# by scanning the projects folder.
webhook_registry: dict[str, dict] = {}

# "<workflow name>::<node name>" -> {"workflow", "node_name", "interval_seconds",
# "daily_time", "last_run"}. Polled by _scheduler_loop(). Registered the same
# way webhooks are: on boot (scan saved projects) and whenever a workflow is
# deployed via POST /projects/deploy.
schedule_registry: dict[str, dict] = {}
_schedule_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Live event broadcast — lets the editor UI watch webhook-triggered runs as
# they happen (canvas lights up just like the Run button). Each connected UI
# gets its own queue; the webhook handler pushes engine events to all of them.
# ---------------------------------------------------------------------------
_subscribers: list[queue.Queue] = []
_sub_lock = threading.Lock()


def broadcast_event(evt: dict):
    with _sub_lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(evt)
        except Exception:
            pass


def add_subscriber() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=1000)
    with _sub_lock:
        _subscribers.append(q)
    return q


def remove_subscriber(q: queue.Queue):
    with _sub_lock:
        if q in _subscribers:
            _subscribers.remove(q)


def node_catalog() -> list[dict]:
    out = []
    for type_id, cls in sorted(engine.registry.items()):
        out.append({
            "type": type_id,
            "title": cls.TITLE,
            "category": cls.CATEGORY,
            "inputs": cls.INPUTS,
            "outputs": cls.OUTPUTS,
            "params": getattr(cls, "PARAMS", []),
        })
    # ---- robotics / device nodes (servo projects) ----
    # These don't run in the engine — they generate Arduino code. They're
    # served here so the editor can show them in a ROBOTICS palette section.
    try:
        import codegen
        dev_reg = codegen.discover_device_nodes(None, NODES_DIR)
        for type_id, cls in sorted(dev_reg.items()):
            out.append({
                "type": type_id,
                "title": cls.TITLE,
                "category": getattr(cls, "CATEGORY", "robotics"),
                "inputs": cls.INPUTS,
                "outputs": cls.OUTPUTS,
                "params": getattr(cls, "PARAMS", []),
                "device": True,          # marks it as a code-generating node
            })
    except Exception as e:
        print(f"  [warn] could not load device nodes: {e}")
    return out


def generate_sketch(workflow: dict) -> str:
    """Compile a servo project's graph into Arduino .ino source."""
    import codegen
    reg = codegen.discover_device_nodes(None, NODES_DIR)
    return codegen.generate(workflow, reg)


def register_webhooks_from_workflow(workflow: dict):
    """Scan a workflow for webhook.trigger nodes and register their paths.
    Returns the list of paths registered."""
    registered = []
    for n in workflow.get("nodes", []):
        if n.get("type") == "webhook.trigger":
            path = (n.get("params", {}).get("path") or "/webhook").strip()
            if not path.startswith("/"):
                path = "/" + path
            method = (n.get("params", {}).get("method") or "ANY").upper()
            webhook_registry[path] = {
                "workflow": workflow,
                "node_name": n["name"],
                "method": method,
            }
            registered.append(path)
            print(f"  [webhook] registered {method} /hook{path} -> '{n['name']}' in '{workflow.get('name','?')}'")
    return registered


def register_all_saved_webhooks():
    """On boot, scan every saved project for webhook triggers."""
    if not os.path.isdir(PROJECTS_DIR):
        return
    for fname in os.listdir(PROJECTS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(PROJECTS_DIR, fname)) as f:
                wf = json.load(f)
            register_webhooks_from_workflow(wf)
        except Exception as e:
            print(f"  [warn] could not scan {fname} for webhooks: {e}")


def register_schedules_from_workflow(workflow: dict):
    """Scan a workflow for enabled trigger.schedule nodes and (re)register
    them. Any previously-registered schedules for this same workflow name
    are dropped first, so redeploying with a changed/removed schedule node
    doesn't leave a stale timer running."""
    from nodes.trigger_schedule import ScheduleTriggerNode  # local import: nodes/ isn't a package until NODES_DIR is on sys.path
    wf_name = workflow.get("name", "?")
    with _schedule_lock:
        for key in [k for k, v in schedule_registry.items() if v["workflow"].get("name") == wf_name]:
            del schedule_registry[key]
        registered = []
        for n in workflow.get("nodes", []):
            if n.get("type") != "trigger.schedule":
                continue
            params = n.get("params", {}) or {}
            if not params.get("enabled", True):
                continue
            node = ScheduleTriggerNode(n["name"], params)
            key = f"{wf_name}::{n['name']}"
            schedule_registry[key] = {
                "workflow": workflow,
                "node_name": n["name"],
                "interval_seconds": node.interval_seconds(),
                "daily_time": node.daily_time(),
                "last_run": None,        # epoch seconds, interval mode
                "last_run_date": None,   # "YYYY-MM-DD", daily mode
            }
            registered.append(n["name"])
            mode = params.get("mode", "interval")
            detail = f"every {params.get('every',5)} {params.get('unit','minutes')}" if mode == "interval" else f"daily at {params.get('at','08:00')}"
            print(f"  [schedule] registered '{n['name']}' in '{wf_name}' -> {detail}")
    return registered


def register_all_saved_schedules():
    """On boot, scan every saved project for schedule triggers."""
    if not os.path.isdir(PROJECTS_DIR):
        return
    for fname in os.listdir(PROJECTS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(PROJECTS_DIR, fname)) as f:
                wf = json.load(f)
            register_schedules_from_workflow(wf)
        except Exception as e:
            print(f"  [warn] could not scan {fname} for schedules: {e}")


def _fire_schedule(key: str, entry: dict):
    """Runs a due schedule's workflow from its trigger.schedule node,
    the same way a webhook hit runs a workflow from its webhook.trigger
    node — broadcasting events so a connected editor UI can watch it."""
    workflow = json.loads(json.dumps(entry["workflow"]))  # deep copy
    wf_name = workflow.get("name", "?")
    node_name = entry["node_name"]
    broadcast_event({"kind": "schedule_run_start", "workflow": wf_name, "node": node_name})

    def _relay(evt):
        evt = dict(evt); evt["workflow"] = wf_name; evt["source"] = "schedule"
        broadcast_event(evt)

    try:
        engine.registry = discover_nodes(NODES_DIR)
        engine.run_workflow(workflow, start_node=node_name, on_event=_relay)
    except Exception as e:
        import traceback
        traceback.print_exc()
        broadcast_event({"kind": "schedule_run_error", "workflow": wf_name, "node": node_name, "error": str(e)})


def _schedule_due(entry: dict, now: float) -> bool:
    if entry["interval_seconds"] is not None:
        return entry["last_run"] is None or (now - entry["last_run"]) >= entry["interval_seconds"]
    if entry["daily_time"] is not None:
        import datetime as _dt
        local = _dt.datetime.fromtimestamp(now)
        hh, mm = entry["daily_time"]
        today = local.strftime("%Y-%m-%d")
        return local.hour == hh and local.minute == mm and entry["last_run_date"] != today
    return False


def _mark_fired(entry: dict, now: float):
    entry["last_run"] = now
    if entry["daily_time"] is not None:
        import datetime as _dt
        entry["last_run_date"] = _dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d")


def _scheduler_loop(poll_seconds: float = 1.0):
    """Background thread: wakes up every `poll_seconds` and fires any
    registered schedule that's due. Runs for as long as api.py runs —
    exactly the limitation trigger_schedule.py's docstring describes."""
    while True:
        now = time.time()
        with _schedule_lock:
            due = [(k, v) for k, v in schedule_registry.items() if _schedule_due(v, now)]
            for _, entry in due:
                _mark_fired(entry, now)
        for key, entry in due:
            threading.Thread(target=_fire_schedule, args=(key, entry), daemon=True).start()
        time.sleep(poll_seconds)


def mark_respond_nodes_as_real(workflow: dict):
    """Flip 'is_test_run' to True on every webhook.respond node so it
    actually raises the signal instead of passing data through (used only
    when a REAL hook hits, not when testing from the editor)."""
    for n in workflow.get("nodes", []):
        if n.get("type") == "webhook.respond":
            n.setdefault("params", {})["is_test_run"] = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("  api: " + (fmt % args) + "\n")

    def _send(self, code: int, payload, is_raw=False):
        if is_raw:
            body = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
            ctype = "text/plain"
        else:
            body = json.dumps(payload).encode("utf-8")
            ctype = "application/json"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            self._send(200, {"status": "ok"})
        elif path == "/nodes":
            engine.registry = discover_nodes(NODES_DIR)
            self._send(200, {"nodes": node_catalog()})
        elif path == "/webhooks":
            self._send(200, {"registered": [
                {"path": p, "method": v["method"], "node": v["node_name"], "workflow": v["workflow"].get("name")}
                for p, v in webhook_registry.items()
            ]})
        elif path == "/schedules":
            self._send(200, {"registered": [
                {"key": k, "node": v["node_name"], "workflow": v["workflow"].get("name"),
                 "interval_seconds": v["interval_seconds"], "daily_time": v["daily_time"],
                 "last_run": v["last_run"]}
                for k, v in schedule_registry.items()
            ]})
        elif path.startswith("/hook/"):
            self._handle_webhook_hit(path[5:], "GET", parsed)
        elif path == "/events":
            self._handle_events_stream()
        else:
            self._send(404, {"error": "not found", "path": path})

    def _handle_events_stream(self):
        """Server-Sent-Events stream of live run events (currently webhook
        runs). The editor UI subscribes here so its canvas can light up when
        a webhook fires."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        q = add_subscriber()
        try:
            # initial comment so the client knows it's connected
            self.wfile.write(b": connected\n\n"); self.wfile.flush()
            while True:
                try:
                    evt = q.get(timeout=15)
                except Exception:
                    # heartbeat keeps the connection alive through idle periods
                    try:
                        self.wfile.write(b": ping\n\n"); self.wfile.flush()
                        continue
                    except Exception:
                        break
                try:
                    self.wfile.write(f"data: {json.dumps(evt)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    break
        finally:
            remove_subscriber(q)

    def _do_any(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/run":
            self._handle_run()
        elif path == "/generate":
            self._handle_generate()
        elif path == "/run-stream":
            self._handle_run_stream()
        elif path == "/webhooks/register":
            self._handle_register()
        elif path == "/projects/deploy":
            self._handle_deploy()
        elif path.startswith("/hook/"):
            self._handle_webhook_hit(path[5:], method, parsed)
        else:
            self._send(404, {"error": "not found", "path": path})

    def do_POST(self):
        self._do_any("POST")

    def do_PUT(self):
        self._do_any("PUT")

    def do_PATCH(self):
        self._do_any("PATCH")

    def do_DELETE(self):
        self._do_any("DELETE")

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return None, b""
        # transparently handle gzip/deflate-compressed bodies (many HTTP
        # clients and webhook senders compress by default)
        encoding = (self.headers.get("Content-Encoding") or "").lower()
        data = raw
        if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
            try:
                import gzip
                data = gzip.decompress(raw)
            except Exception:
                data = raw
        elif encoding == "deflate":
            try:
                import zlib
                data = zlib.decompress(raw)
            except Exception:
                try:
                    import zlib
                    data = zlib.decompress(raw, -zlib.MAX_WBITS)
                except Exception:
                    data = raw
        # try to parse JSON; on ANY failure (bad JSON, binary, bad encoding)
        # return the decoded text instead of crashing the request thread.
        try:
            return json.loads(data), data
        except Exception:
            try:
                return None, data.decode("utf-8", "replace").encode("utf-8")
            except Exception:
                return None, raw

    def _handle_generate(self):
        """Compile a servo project into an Arduino sketch and save it."""
        body, raw = self._read_json_body()
        if body is None and raw:
            self._send(400, {"error": "invalid JSON"}); return
        workflow = body or {}
        try:
            code = generate_sketch(workflow)
            from storage import save_sketch
            name = workflow.get("name", "sketch")
            path = save_sketch(name, code)
            self._send(200, {"ok": True, "path": path, "code": code})
        except Exception as e:
            import traceback; traceback.print_exc()
            self._send(500, {"ok": False, "error": str(e)})

    def _handle_run(self):
        body, raw = self._read_json_body()
        if body is None and raw:
            self._send(400, {"error": "invalid JSON"}); return
        workflow = body or {}
        try:
            engine.registry = discover_nodes(NODES_DIR)
            results = engine.run_workflow(workflow)
            self._send(200, {"ok": True, "results": results})
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})

    def _handle_run_stream(self):
        """Run a workflow and stream execution events as Server-Sent Events.
        Each event is a line:  data: {json}\\n\\n
        The engine's on_event callback writes here as nodes actually execute,
        so the client sees real timing (a Wait node pauses the stream at its
        own position, etc.). The final event carries the full results."""
        body, raw = self._read_json_body()
        if body is None and raw:
            self._send(400, {"error": "invalid JSON"}); return
        workflow = body or {}

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def push(evt):
            try:
                self.wfile.write(f"data: {json.dumps(evt)}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass

        try:
            engine.registry = discover_nodes(NODES_DIR)
            results = engine.run_workflow(workflow, on_event=push)
            push({"kind": "results", "results": results})
        except Exception as e:
            push({"kind": "fatal", "error": str(e)})

    def _handle_register(self):
        body, raw = self._read_json_body()
        if body is None:
            self._send(400, {"error": "invalid JSON"}); return
        try:
            register_webhooks_from_workflow(body)
            paths = [n.get("params", {}).get("path", "/webhook")
                     for n in body.get("nodes", []) if n.get("type") == "webhook.trigger"]
            self._send(200, {"ok": True, "registered_paths": paths})
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})

    def _handle_deploy(self):
        """POST /projects/deploy — body = a normal (non-servo) project's
        workflow JSON. Saves it into this server's data volume (so it
        survives restarts) and immediately hot-registers any webhook/
        schedule triggers it has, no restart required. This is the 'press
        deploy on the project' step: the editor UI sends the currently
        open, saved workflow here, and from that point on this API runs it
        on its own — the desktop UI doesn't need to stay open.

        Servo/hardware projects are rejected here on purpose: they don't
        run in this engine at all, they compile to Arduino code via
        POST /generate instead."""
        body, raw = self._read_json_body()
        if body is None:
            self._send(400, {"error": "invalid JSON"}); return
        name = body.get("name")
        if not name:
            self._send(400, {"error": "workflow is missing a 'name'"}); return
        if body.get("kind") == "servo":
            self._send(400, {
                "ok": False,
                "error": "servo/hardware projects don't deploy here — they compile to "
                         "an Arduino sketch instead",
                "hint": "use POST /generate for servo projects",
            })
            return
        try:
            save_project(name, body)
            webhook_paths = register_webhooks_from_workflow(body)
            schedule_names = register_schedules_from_workflow(body)
            self._send(200, {
                "ok": True,
                "name": name,
                "registered_webhooks": webhook_paths,
                "registered_schedules": schedule_names,
            })
        except Exception as e:
            import traceback; traceback.print_exc()
            self._send(500, {"ok": False, "error": str(e)})

    def _handle_webhook_hit(self, path, method, parsed):
        if not path.startswith("/"):
            path = "/" + path
        entry = webhook_registry.get(path)
        if entry is None:
            self._send(404, {"error": f"no webhook registered for {path}",
                              "hint": "save/open the project in the editor so it auto-registers, "
                                      "or POST the workflow to /webhooks/register"})
            return
        if entry["method"] != "ANY" and entry["method"] != method:
            self._send(405, {"error": f"webhook at {path} expects {entry['method']}, got {method}"})
            return

        body_json, raw = self._read_json_body() if method in ("POST", "PUT", "PATCH", "DELETE") else (None, b"")
        if body_json is None and raw:
            body_json = raw.decode("utf-8", errors="replace")

        query = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}
        headers = {k: v for k, v in self.headers.items()}

        request_data = {
            "method": method,
            "path": path,
            "query": query,
            "headers": headers,
            "body": body_json,
        }

        workflow = json.loads(json.dumps(entry["workflow"]))  # deep copy
        mark_respond_nodes_as_real(workflow)

        wf_name = workflow.get("name", "?")
        # tell any listening UI which workflow is about to run via webhook,
        # so it can switch to / highlight the right canvas.
        broadcast_event({"kind": "webhook_run_start", "workflow": wf_name, "path": path})

        def _relay(evt):
            # tag each engine event with the workflow + source so the UI can
            # replay it on the matching canvas
            evt = dict(evt); evt["workflow"] = wf_name; evt["source"] = "webhook"
            broadcast_event(evt)

        try:
            engine.registry = discover_nodes(NODES_DIR)
            results = engine.run_workflow(workflow, start_node=entry["node_name"],
                                          start_data=request_data, on_event=_relay)
        except Exception as e:
            import traceback
            traceback.print_exc()
            broadcast_event({"kind": "webhook_run_error", "workflow": wf_name, "error": str(e)})
            try:
                self._send(500, {"ok": False, "error": str(e),
                                 "where": "workflow execution"})
            except Exception:
                pass
            return

        try:
            webhook_resp = results.get("__webhook_response__")
            if webhook_resp:
                self._send(webhook_resp["status"], webhook_resp["body"])
            else:
                # no Respond node was reached — auto-ack
                self._send(200, {"ok": True, "note": "workflow finished, no Respond to Webhook node was hit"})
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                self._send(500, {"ok": False, "error": str(e), "where": "sending response"})
            except Exception:
                pass


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DUGS_API_HOST", "127.0.0.1")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("DUGS_API_PORT", "5800"))
    register_all_saved_webhooks()
    register_all_saved_schedules()
    threading.Thread(target=_scheduler_loop, daemon=True).start()
    server = ThreadingHTTPServer((host, port), Handler)
    print("=" * 44)
    print("  dugs — api server")
    print("=" * 44)
    print(f"  listening on http://{host}:{port}")
    print(f"  nodes dir:   {NODES_DIR}")
    print(f"  data dir:    {os.path.dirname(PROJECTS_DIR)}")
    print( "  endpoints:   GET /health  GET /nodes  POST /run")
    print( "               POST /webhooks/register  GET /webhooks")
    print( "               POST /projects/deploy     <- 'deploy' a workflow so this API runs it on its own")
    print( "               GET /schedules")
    print( "               ANY  /hook/<path>   <- real webhook hits land here")
    print( "  (ctrl-c to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")


if __name__ == "__main__":
    main()
