"""
codegen.py — turns a SERVO project's node graph into an Arduino .ino sketch.

It walks the graph from the start node, following connections, and asks each
device node for its four code contributions (includes / globals / setup / loop).
Those get stitched into a standard Arduino sketch:

    #include ...            <- from includes()
    <globals>               <- from globals()

    void setup() {
      <setup lines>         <- from setup()
    }

    void loop() {
      <loop lines>          <- from loop(), in graph order
    }

Repeat nodes are "block" nodes: everything downstream of them is wrapped inside
the for-loop they open, and the block is closed at the end.

Includes / globals / setup lines are de-duplicated, so two Servo nodes on the
same pin don't emit the header (or the attach) twice.
"""
import inspect
import importlib.util
import os
import sys

from device_base import DeviceNode


def discover_device_nodes(module_path: str, nodes_dir: str | None = None) -> dict:
    """Load every DeviceNode subclass.

    Looks in device_nodes.py AND (optionally) the nodes/ folder, so hardware
    nodes can live as individual files in nodes/ just like engine nodes do.
    """
    registry = {}

    def _scan(path, modname):
        try:
            spec = importlib.util.spec_from_file_location(modname, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, DeviceNode) and obj is not DeviceNode and hasattr(obj, "TYPE"):
                    registry[obj.TYPE] = obj
        except Exception as e:
            print(f"  [codegen warn] could not load {os.path.basename(path)}: {e}")

    if module_path and os.path.exists(module_path):
        _scan(module_path, "device_nodes")

    if nodes_dir and os.path.isdir(nodes_dir):
        for fname in sorted(os.listdir(nodes_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            _scan(os.path.join(nodes_dir, fname), f"devnode_{fname[:-3]}")

    return registry


def _exec_order(workflow: dict) -> list[str]:
    """Walk the graph from the start node(s) in connection order."""
    nodes = workflow.get("nodes", [])
    conns = workflow.get("connections", {})
    names = [n["name"] for n in nodes]

    has_incoming = set()
    for src, links in conns.items():
        for l in links:
            has_incoming.add(l["to"])
    starts = [n for n in names if n not in has_incoming] or names[:1]

    order, seen = [], set()
    stack = list(reversed(starts))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        order.append(cur)
        # follow outgoing links in order
        for l in conns.get(cur, []):
            if l["to"] not in seen:
                stack.append(l["to"])
    return order


def _chain_from(start: str, workflow: dict) -> list[str]:
    """Walk the graph forward from `start`, returning the node names in order
    (excluding the start node itself)."""
    conns = workflow.get("connections", {})
    order, seen = [], {start}
    stack = [l["to"] for l in conns.get(start, [])]
    while stack:
        cur = stack.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        order.append(cur)
        for l in conns.get(cur, []):
            if l["to"] not in seen:
                stack.append(l["to"])
    return order


def _targets(name, workflow, port=0):
    """Nodes wired to a specific OUTPUT PORT of `name`."""
    out = []
    for l in workflow.get("connections", {}).get(name, []):
        if l.get("out", 0) == port:
            out.append(l["to"])
    return out


def generate(workflow: dict, registry: dict) -> str:
    """Build the full .ino source for a servo project.

    An Arduino sketch has two entry points:
        setup()  -> runs once at power-on
        loop()   -> repeats forever

    The 'On Start' and 'On Repeat' trigger nodes decide which block a chain of
    nodes compiles into. If there is NO trigger node, everything falls into
    loop() (so old graphs keep working).

    Branch nodes (If) emit a real C++ if/else, with each output port's chain
    nested inside the matching block.
    """
    nodes_by_name = {n["name"]: n for n in workflow.get("nodes", [])}

    includes: list[str] = []
    pin_defs: list[str] = []
    globs: list[str] = []
    setup_decl: list[str] = []
    setup_body: list[str] = []
    loop_body: list[str] = []
    unknown: list[str] = []

    def add_unique(target, items):
        for it in items:
            if it not in target:
                target.append(it)

    # ---- declarations first: pin maps, arrays, servo banks. Everything else
    # refers to these by name, so they must exist before any code that uses
    # them. They also contribute includes and setup lines (a servo bank has to
    # attach all its servos at power-on).
    for spec in workflow.get("nodes", []):
        if spec["type"] in ("device.pins", "device.array", "device.servo_array"):
            cls = registry.get(spec["type"])
            if cls:
                dnode = cls(spec["name"], dict(spec.get("params", {})))
                add_unique(pin_defs, dnode.globals())
                add_unique(includes, dnode.includes())
                add_unique(setup_decl, dnode.setup())

    def collect(node):
        add_unique(includes, node.includes())
        add_unique(globs, node.globals())
        add_unique(setup_decl, node.setup())

    def emit_from(name, out_lines, indent, visited):
        """Emit `name` and everything downstream of it, recursively.
        Handles branch nodes (if/else) and block nodes (for-loops)."""
        while name:
            if name in visited:
                return
            visited.add(name)
            spec = nodes_by_name.get(name)
            if not spec:
                return
            if spec["type"] in ("device.pins", "device.array", "device.servo_array"):
                nxt = _targets(name, workflow, 0)
                name = nxt[0] if nxt else None
                continue
            # State nodes are emitted by the switch builder, not inline
            if spec["type"] == "device.state":
                return

            cls = registry.get(spec["type"])
            if cls is None:
                unknown.append(f"{name} ({spec['type']})")
                return
            node = cls(name, dict(spec.get("params", {})))
            collect(node)
            pad = "  " * indent
            out_lines.append(f"{pad}// --- {name} ---")

            # ---- BRANCH: real if / else ----
            if getattr(cls, "IS_BRANCH", False):
                out_lines.append(f"{pad}if ({node.condition()}) {{")
                # a Timer restarts itself the moment it fires, so it can run
                # again on the next pass
                if hasattr(node, "rearm"):
                    out_lines.append(f"{pad}  {node.rearm()}")
                for t in _targets(name, workflow, 0):      # port 0 = TRUE / done
                    emit_from(t, out_lines, indent + 1, set(visited))
                false_targets = _targets(name, workflow, 1)  # port 1 = FALSE
                if false_targets:
                    out_lines.append(f"{pad}}} else {{")
                    for t in false_targets:
                        emit_from(t, out_lines, indent + 1, set(visited))
                out_lines.append(f"{pad}}}")
                return     # both branches consumed everything downstream

            # ---- BLOCK: for-loop wrapping everything after it ----
            if getattr(cls, "IS_BLOCK", False):
                for l in node.loop_open():
                    out_lines.append(f"{pad}{l}")
                for t in _targets(name, workflow, 0):
                    emit_from(t, out_lines, indent + 1, set(visited))
                for l in node.loop_close():
                    out_lines.append(f"{pad}{l}")
                return

            # ---- plain node ----
            for l in node.loop():
                out_lines.append(f"{pad}{l}")
            nxt = _targets(name, workflow, 0)
            name = nxt[0] if nxt else None

    starts = [n["name"] for n in workflow.get("nodes", []) if n["type"] == "device.on_start"]
    repeats = [n["name"] for n in workflow.get("nodes", []) if n["type"] == "device.on_repeat"]

    # ---- state machine: collect all State nodes ----
    state_nodes = [n for n in workflow.get("nodes", []) if n["type"] == "device.state"]
    state_names = []
    for sn in state_nodes:
        cls = registry.get("device.state")
        nm = cls(sn["name"], dict(sn.get("params", {}))).state_name()
        if nm not in state_names:
            state_names.append(nm)

    if state_names:
        # enum of every state + the current-state variable, starting in the first
        globs.insert(0, f"enum State {{ {', '.join(state_names)} }};")
        globs.insert(1, f"State state = {state_names[0]};")

    if not starts and not repeats:
        for n in _exec_order(workflow)[:1]:
            emit_from(n, loop_body, 1, set())
    else:
        for s in starts:
            for t in _targets(s, workflow, 0):
                emit_from(t, setup_body, 1, set())
        for r in repeats:
            for t in _targets(r, workflow, 0):
                emit_from(t, loop_body, 1, set())

    # ---- if there are states, wrap them in a switch inside loop() ----
    if state_names:
        sw = ["  switch (state) {"]
        for sn in state_nodes:
            cls = registry.get("device.state")
            nm = cls(sn["name"], dict(sn.get("params", {}))).state_name()
            sw.append(f"    case {nm}: {{")
            body = []
            for t in _targets(sn["name"], workflow, 0):
                emit_from(t, body, 3, set())
            sw.extend(body)
            sw.append("      break;")
            sw.append("    }")
        sw.append("  }")
        # states replace whatever On Repeat produced (they ARE the loop body)
        loop_body = sw

    name = workflow.get("name", "sketch")
    out = []
    out.append(f"// ===== generated by DUGS from project '{name}' =====")
    out.append("// Edit the graph in DUGS and re-export; changes here get overwritten.")
    out.append("")
    for i in includes:
        out.append(i)
    if includes:
        out.append("")
    if pin_defs:
        out.append("// ---- pin map ----")
        for d in pin_defs:
            out.append(d)
        out.append("")
    for g in globs:
        out.append(g)
    if globs:
        out.append("")

    out.append("// runs ONCE at power-on")
    out.append("void setup() {")
    for l in setup_decl:
        out.append(f"  {l}")
    if setup_body:
        out.append("")
        out.extend(setup_body)
    out.append("}")
    out.append("")

    out.append("// runs OVER AND OVER, forever")
    out.append("void loop() {")
    if loop_body:
        out.extend(loop_body)
    else:
        out.append("  // (nothing wired to an 'On Repeat' node)")
    out.append("}")
    out.append("")

    if unknown:
        out.append("// NOTE: these nodes were skipped (not hardware nodes):")
        for u in unknown:
            out.append(f"//   - {u}")

    return "\n".join(out)
