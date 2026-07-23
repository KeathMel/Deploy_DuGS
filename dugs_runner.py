"""
dugs_runner.py — runs saved workflows on their own triggers.

This is the "leave it running somewhere" half of DuGS. No GUI, no build step,
no dependencies beyond Python itself. Point it at a folder of workflows and it
does whatever each workflow's own trigger says:

    Webhook trigger   -> listens for HTTP and fires on a hit
    Schedule trigger  -> fires on its interval / daily time
    Manual trigger    -> only runs when you ask it to

Runs anywhere Python runs — a Pi, a phone under Termux, a VPS, a container.

SELF-CONTAINED
==============
Everything needed to run a workflow ships here: the engine, the node contract
and the nodes themselves. No desktop app, no Qt, no GUI. You build workflows in
the DuGS app on your own machine, then drop the exported .json into projects/
here and this runs it.

Adding a node is dropping a .py file into nodes/ and restarting — no rebuild,
no new image.

USAGE
=====
    python3 dugs_runner.py                     # everything, defaults
    python3 dugs_runner.py --run my_workflow   # run one workflow now and exit
    python3 dugs_runner.py --list              # show what's loaded and its trigger
    python3 dugs_runner.py --port 5800 --host 0.0.0.0

ENVIRONMENT
===========
    DUGS_DATA_DIR   where projects/ lives              (default: next to this file)
    DUGS_HOST       http bind address                  (default: 0.0.0.0)
    DUGS_PORT       http port                          (default: 5800)
"""
import os
import sys
import json
import time
import argparse
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------- paths
HERE = os.path.dirname(os.path.abspath(__file__))
# the engine and nodes ship alongside this file — nothing to mount, nothing to
# point at. DUGS_APP_DIR still works if you want to run against a DuGS checkout
# instead of the copy here.
APP_DIR = os.environ.get("DUGS_APP_DIR", HERE)
DATA_DIR = os.environ.get("DUGS_DATA_DIR", HERE)
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
HOST = os.environ.get("DUGS_HOST", "0.0.0.0")
PORT = int(os.environ.get("DUGS_PORT", "5800"))

# the app folder has to be importable so engine.py and the nodes resolve
sys.path.insert(0, APP_DIR)


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- engine
def load_engine():
    """Import the engine from the mounted app folder.

    Kept in a function (not a top-level import) so a missing/incomplete app
    folder produces a clear message instead of a traceback on startup.
    """
    try:
        from engine import Engine
    except Exception as e:
        log(f"FATAL: could not import engine from {APP_DIR}: {e}")
        raise SystemExit(1)
    nodes_dir = os.path.join(APP_DIR, "nodes")
    if not os.path.isdir(nodes_dir):
        log(f"FATAL: no nodes/ folder in {APP_DIR}")
        raise SystemExit(1)
    eng = Engine(nodes_dir)
    log(f"engine ready — {len(eng.registry)} node types from {nodes_dir}")
    return eng


# ---------------------------------------------------------------- workflows
def load_workflows():
    """Every saved workflow, skipping servo projects (they generate Arduino
    code rather than running here)."""
    out = {}
    if not os.path.isdir(PROJECTS_DIR):
        log(f"no projects folder at {PROJECTS_DIR} — nothing to run yet")
        return out
    for fname in sorted(os.listdir(PROJECTS_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(PROJECTS_DIR, fname)
        try:
            with open(path) as f:
                wf = json.load(f)
        except Exception as e:
            log(f"  skipped {fname}: {e}")
            continue
        if wf.get("kind") == "servo":
            continue          # hardware project, not something we run
        out[wf.get("name") or fname[:-5]] = wf
    return out


def triggers_of(wf):
    """The trigger nodes in a workflow, as (node_name, type, params)."""
    found = []
    for n in wf.get("nodes", []):
        t = n.get("type", "")
        if t.startswith("trigger.") or t == "webhook.trigger":
            found.append((n["name"], t, n.get("params", {})))
    return found


# ---------------------------------------------------------------- running
_run_lock = threading.Lock()


def run_workflow(engine, wf, start_node=None, start_data=None):
    """Run one workflow. Serialised, so two triggers firing at once cannot
    interleave and corrupt each other's state."""
    name = wf.get("name", "(unnamed)")
    with _run_lock:
        t0 = time.perf_counter()
        try:
            result = engine.run_workflow(wf, start_node=start_node,
                                         start_data=start_data)
            ms = (time.perf_counter() - t0) * 1000
            log(f"ran '{name}' in {ms:.0f}ms")
            return result
        except Exception as e:
            log(f"ERROR running '{name}': {e}")
            return {"error": str(e)}


# ---------------------------------------------------------------- schedules
def _next_fire(params, last):
    """When a schedule trigger should next fire."""
    mode = params.get("mode", "interval")
    if mode == "daily":
        at = str(params.get("at", "09:00"))
        try:
            hh, mm = [int(x) for x in at.split(":")[:2]]
        except Exception:
            hh, mm = 9, 0
        now = datetime.now()
        nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        return nxt
    every = float(params.get("every", 5) or 5)
    unit = params.get("unit", "minutes")
    seconds = every * {"seconds": 1, "minutes": 60, "hours": 3600}.get(unit, 60)
    return (last or datetime.now()) + timedelta(seconds=max(1.0, seconds))


def scheduler_loop(engine, schedules, stop):
    """One thread watching every schedule trigger. Sleeps in short ticks so it
    stays responsive to shutdown instead of oversleeping a stop signal."""
    while not stop.is_set():
        now = datetime.now()
        for s in schedules:
            if now >= s["next"]:
                log(f"schedule fired: '{s['workflow']}' ({s['node']})")
                run_workflow(engine, s["wf"], start_node=s["node"],
                             start_data={"triggered_at": now.isoformat()})
                s["last"] = now
                s["next"] = _next_fire(s["params"], now)
        stop.wait(1.0)


# ---------------------------------------------------------------- http
class Handler(BaseHTTPRequestHandler):
    engine = None
    hooks = {}          # (method, path) -> {"workflow", "node", "wf"}
    workflows = {}

    def log_message(self, *a):
        pass            # quiet: we do our own logging

    # ---- helpers ----
    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n) if n else b""
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _match(self, method, path):
        """Find a webhook registered for this request, honouring ANY."""
        for m in (method, "ANY"):
            hit = self.hooks.get((m, path))
            if hit:
                return hit
        return None

    # ---- routes ----
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self._send(200, {"ok": True,
                                    "workflows": len(self.workflows),
                                    "webhooks": len(self.hooks)})
        if path == "/workflows":
            return self._send(200, {"workflows": sorted(self.workflows)})
        hit = self._match("GET", path)
        if hit:
            return self._fire(hit, {"query": self.path})
        self._send(404, {"error": "no webhook at this path"})

    def do_POST(self):
        path = self.path.split("?")[0]
        # run a workflow by name, whatever its trigger is
        if path.startswith("/run/"):
            name = path[len("/run/"):]
            wf = self.workflows.get(name)
            if wf is None:
                return self._send(404, {"error": f"no workflow named '{name}'"})
            result = run_workflow(self.engine, wf, start_data=self._body())
            return self._send(200, {"ok": True, "result": _safe(result)})
        hit = self._match("POST", path)
        if hit:
            return self._fire(hit, self._body())
        self._send(404, {"error": "no webhook at this path"})

    def do_PUT(self):
        self.do_POST()

    def do_DELETE(self):
        hit = self._match("DELETE", self.path.split("?")[0])
        if hit:
            return self._fire(hit, self._body())
        self._send(404, {"error": "no webhook at this path"})

    def _fire(self, hit, data):
        log(f"webhook hit: {self.command} {self.path} -> '{hit['workflow']}'")
        result = run_workflow(self.engine, hit["wf"], start_node=hit["node"],
                              start_data=data)
        # a Respond to Webhook node decides the reply when there is one
        resp = result.get("__webhook_response__") if isinstance(result, dict) else None
        if resp:
            return self._send(resp.get("status", 200), resp.get("body", {}))
        self._send(200, {"ok": True})


def _safe(obj):
    """Make engine output JSON-serialisable, whatever ended up in it."""
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


# ---------------------------------------------------------------- startup
def build_registry(workflows):
    """Sort every workflow's triggers into webhooks and schedules."""
    hooks, schedules, manual = {}, [], []
    for name, wf in workflows.items():
        for node_name, ttype, params in triggers_of(wf):
            if ttype == "webhook.trigger":
                path = str(params.get("path", "/webhook"))
                if not path.startswith("/"):
                    path = "/" + path
                method = str(params.get("method", "POST")).upper()
                hooks[(method, path)] = {"workflow": name, "node": node_name, "wf": wf}
            elif ttype == "trigger.schedule":
                schedules.append({"workflow": name, "node": node_name,
                                  "wf": wf, "params": params,
                                  "last": None,
                                  "next": _next_fire(params, None)})
            else:
                manual.append((name, node_name))
    return hooks, schedules, manual


def main():
    ap = argparse.ArgumentParser(description="Run DuGS workflows on their triggers.")
    ap.add_argument("--run", metavar="NAME", help="run one workflow now and exit")
    ap.add_argument("--list", action="store_true", help="list workflows and their triggers")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()

    print("=" * 52)
    print("  DuGS runner")
    print("=" * 52)
    log(f"app dir  : {APP_DIR}")
    log(f"data dir : {DATA_DIR}")

    engine = load_engine()
    workflows = load_workflows()
    log(f"loaded {len(workflows)} workflow(s)")

    hooks, schedules, manual = build_registry(workflows)

    if args.list:
        for name, wf in sorted(workflows.items()):
            trigs = triggers_of(wf) or [("-", "no trigger", {})]
            for node_name, ttype, _ in trigs:
                print(f"  {name:24} {ttype:20} ({node_name})")
        return

    if args.run:
        wf = workflows.get(args.run)
        if wf is None:
            log(f"no workflow named '{args.run}'")
            raise SystemExit(1)
        run_workflow(engine, wf)
        return

    for (m, p), h in sorted(hooks.items()):
        log(f"webhook  {m:6} {p:24} -> {h['workflow']}")
    for s in schedules:
        log(f"schedule {s['workflow']:24} next {s['next']:%H:%M:%S}")
    for name, node in manual:
        log(f"manual   {name:24} POST /run/{name}")

    stop = threading.Event()
    if schedules:
        threading.Thread(target=scheduler_loop, args=(engine, schedules, stop),
                         daemon=True).start()

    Handler.engine = engine
    Handler.hooks = hooks
    Handler.workflows = workflows
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    log(f"listening on http://{args.host}:{args.port}")
    log("ctrl-c to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("shutting down")
        stop.set()
        server.shutdown()


if __name__ == "__main__":
    main()
