"""
dugs engine.py — discovers nodes, loads workflow JSON, walks the graph.

Workflow JSON shape:
{
  "name": "my workflow",
  "nodes": [
    {"name": "Start", "type": "trigger.manual", "params": {"data": {"x": 1}}},
    {"name": "Add", "type": "core.set", "params": {"mode": "keep", "assignments": [{"name": "y", "value": 2}]}},
    {"name": "Show", "type": "core.log", "params": {"label": "OUT"}}
  ],
  "connections": {
    "Start": [{"to": "Add", "out": 0, "in": 0}],
    "Add":   [{"to": "Show", "out": 0, "in": 0}]
  }
}
"""

from __future__ import annotations
import os
import sys
import json
import time
import importlib.util
import inspect
from node_base import Node


def discover_nodes(nodes_dir: str) -> dict[str, type[Node]]:
    registry: dict[str, type[Node]] = {}
    if not os.path.isdir(nodes_dir):
        return registry
    for fname in os.listdir(nodes_dir):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(nodes_dir, fname)
        try:
            spec = importlib.util.spec_from_file_location(fname[:-3], path)
            module = importlib.util.module_from_spec(spec)
            # make sure node_base is importable from the nodes dir
            sys.path.insert(0, nodes_dir)
            sys.path.insert(0, os.path.dirname(nodes_dir))
            sys.modules[spec.name] = module  # so getattr(sys.modules[...], ...) lookups work later
            spec.loader.exec_module(module)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Node) and obj is not Node and hasattr(obj, "TYPE"):
                    registry[obj.TYPE] = obj
        except Exception as e:
            print(f"  [warn] could not load {fname}: {e}")
    return registry


def _downstream_of(start: str, connections: dict) -> set[str]:
    """All nodes reachable downstream from `start` (following connections).
    Used so that when a loop node fires again, everything inside the loop body
    is allowed to run again too."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        for link in connections.get(cur, []):
            tgt = link["to"]
            if tgt not in seen and tgt != start:
                seen.add(tgt)
                stack.append(tgt)
    return seen


class Engine:
    def __init__(self, nodes_dir: str):
        self.nodes_dir = nodes_dir
        self.registry = discover_nodes(nodes_dir)

    def run_workflow(self, workflow: dict, start_node: str | None = None,
                      start_data: dict | None = None, on_event=None) -> dict:
        """
        start_node / start_data: used by the webhook handler in api.py to kick
        off execution at a specific trigger node with real request data,
        instead of running every start node with empty input.

        on_event(evt: dict): optional callback fired as execution progresses,
        so a UI can show what is happening live (n8n-style). Event kinds:
          {"kind": "start", "nodes": [...names...]}
          {"kind": "node_running", "node": name, "type": type_id, "items_in": N}
          {"kind": "node_done", "node": name, "items_out": N,
                                 "ports": [N0, N1, ...], "ms": float,
                                 "sample": [ ...up to 3 item jsons... ]}
          {"kind": "edge", "from": name, "out": i, "to": name, "in": j, "items": N}
          {"kind": "node_error", "node": name, "error": str}
          {"kind": "done"}
        Failures in on_event are swallowed so they can never break a run.
        """
        def emit(evt):
            if on_event is not None:
                try:
                    on_event(evt)
                except Exception:
                    pass

        nodes_spec = workflow.get("nodes", [])
        connections = workflow.get("connections", {})

        # build instances
        instances: dict[str, Node] = {}
        for n in nodes_spec:
            cls = self.registry.get(n["type"])
            if cls is None:
                raise ValueError(f"Unknown node type: '{n['type']}' — is the node file in nodes/?")
            instances[n["name"]] = cls(n["name"], dict(n.get("params", {})))

        # find start nodes (no incoming connections OR INPUTS==0)
        has_incoming = set()
        for src, links in connections.items():
            for link in links:
                has_incoming.add(link["to"])

        # ---- work out, per target node, how many distinct upstream input
        # ports actually feed it. A node only runs once EVERY connected input
        # port has delivered. This is what Merge (and any multi-input node)
        # relies on: it must wait for all branches before running.
        #
        # "connected input ports" = the set of `in` indices that appear in
        # connections pointing at this node. For a normal single-input node
        # that's just {0}, so it runs as soon as that one port arrives —
        # identical to the old behaviour.
        expected_ports: dict[str, set[int]] = {}
        for src, links in connections.items():
            for link in links:
                tgt = link["to"]
                expected_ports.setdefault(tgt, set()).add(link.get("in", 0))

        # buffers[name][in_port] = accumulated list of items waiting on that port
        buffers: dict[str, dict[int, list]] = {}
        arrived: dict[str, set[int]] = {}

        if start_node:
            seed: list[tuple[str, int, list]] = [
                (start_node, 0, [{"json": start_data or {}}])
            ]
            start_nodes = [start_node]
        else:
            start_nodes = [
                name for name, inst in instances.items()
                if inst.INPUTS == 0 or name not in has_incoming
            ]
            seed = [(name, 0, []) for name in start_nodes]

        results: dict[str, list] = {}

        print(f"\n=== running: {workflow.get('name', '(unnamed)')} ===")
        print(f"starting from: {start_nodes}\n")
        emit({"kind": "start", "nodes": list(start_nodes)})

        # Grab the exact WebhookRespondSignal class object from the already
        # dynamically-loaded webhook.respond node module (NOT a fresh package
        # import — that would create a second, different class object and
        # break isinstance checks below).
        WebhookRespondSignal = None
        respond_cls = self.registry.get("webhook.respond")
        if respond_cls is not None:
            WebhookRespondSignal = getattr(sys.modules.get(respond_cls.__module__), "WebhookRespondSignal", None)

        # delivery queue carries (target_name, in_port, items)
        queue: list[tuple[str, int, list]] = list(seed)
        ran: set[str] = set()

        def deliver(target, in_port, items):
            buffers.setdefault(target, {}).setdefault(in_port, []).extend(items)
            arrived.setdefault(target, set()).add(in_port)

        while queue:
            name, in_port, incoming = queue.pop(0)

            node_cls = instances[name].__class__
            # Loop nodes (ALLOW_RERUN) may execute more than once — this is what
            # makes a feedback loop possible: an IF's "false" branch can wire
            # back into a Loop node and re-trigger it. Every other node keeps
            # the original run-exactly-once behaviour.
            can_rerun = getattr(node_cls, "ALLOW_RERUN", False)
            if name in ran and not can_rerun:
                continue
            if name in ran and can_rerun:
                # starting a fresh pass through the loop: clear this node's
                # previous arrivals/buffers so port gating works again.
                ran.discard(name)
                buffers.pop(name, None)
                arrived.pop(name, None)
                # anything downstream of the loop must also be allowed to run
                # again on this new pass.
                for dn in _downstream_of(name, connections):
                    ran.discard(dn)
                    buffers.pop(dn, None)
                    arrived.pop(dn, None)

            deliver(name, in_port, incoming)

            # Has every connected input port for this node arrived yet?
            need = expected_ports.get(name, {0})
            got = arrived.get(name, set())
            if not need.issubset(got):
                # still waiting on at least one upstream branch — defer.
                continue

            ran.add(name)
            node = instances[name]

            # assemble inputs as an ordered list of per-port item lists
            nbuf = buffers.get(name, {})
            max_port = max(need | {0})
            input_ports = [nbuf.get(i, []) for i in range(max_port + 1)]

            # Multi-input nodes (INPUTS != 1) get the full per-port structure;
            # ordinary nodes get the flat item list on port 0, exactly as before.
            declared_inputs = getattr(node, "INPUTS", 1)
            if declared_inputs == 1:
                run_arg = input_ports[0]
            else:
                run_arg = input_ports

            total_in = sum(len(p) for p in input_ports)
            print(f"--> {node.TYPE} '{name}'  ({total_in} items in across {len(need)} port(s))")
            emit({"kind": "node_running", "node": name,
                  "type": node.TYPE, "items_in": total_in})

            # build the cross-node context: {node_name: [items...]} from every
            # node that has produced output so far, so expressions like
            # {{ $('Other Node').item.json.x }} can resolve. Each node's first
            # output port is exposed as its items.
            context = {}
            for done_name, done_ports in results.items():
                if done_ports and isinstance(done_ports[0], list):
                    context[done_name] = done_ports[0]
                elif isinstance(done_ports, list):
                    context[done_name] = done_ports
            node._context = context

            t0 = time.perf_counter()
            errored = False
            try:
                output = node.run(run_arg)
            except Exception as e:
                if WebhookRespondSignal is not None and isinstance(e, WebhookRespondSignal):
                    print(f"    [respond] status={e.status}")
                    results[name] = [[{"json": e.body}]]
                    ms = (time.perf_counter() - t0) * 1000
                    emit({"kind": "node_done", "node": name, "items_out": 1,
                          "ports": [1], "ms": ms, "sample": [e.body]})
                    emit({"kind": "done"})
                    print("\n=== done (responded) ===")
                    return {"__webhook_response__": {"status": e.status, "body": e.body}, **results}
                print(f"    [ERROR] {e}")
                emit({"kind": "node_error", "node": name, "error": str(e)})
                errored = True
                output = [{"json": {"error": str(e), "node": name}}]

            # normalise: single port vs multiple ports
            if output and isinstance(output[0], list):
                ports = output
            else:
                ports = [output]
            results[name] = ports

            ms = (time.perf_counter() - t0) * 1000
            port_counts = [len(p) for p in ports]
            total_out = sum(port_counts)
            # small sample of output items for the live peek (first port, ≤3)
            first_port = ports[0] if ports else []
            sample = [it.get("json", {}) for it in first_port[:3]]
            if not errored:
                emit({"kind": "node_done", "node": name, "items_out": total_out,
                      "ports": port_counts, "ms": ms, "sample": sample})

            # push to connected nodes, honouring the destination input port
            for link in connections.get(name, []):
                out_port = link.get("out", 0)
                dst_in = link.get("in", 0)
                target = link["to"]
                items_for_target = ports[out_port] if out_port < len(ports) else []
                # A back-edge into a loop node carrying ZERO items means that
                # branch didn't match (e.g. an IF's false output was empty), so
                # there is nothing to loop with — don't re-trigger the loop, or
                # it would spin forever on empty deliveries.
                tgt_cls = instances[target].__class__ if target in instances else None
                if (not items_for_target
                        and tgt_cls is not None
                        and getattr(tgt_cls, "ALLOW_RERUN", False)
                        and target in ran):
                    print(f"    -> '{target}' skipped (0 items, loop not re-triggered)")
                    continue
                print(f"    -> '{target}'[in {dst_in}] ({len(items_for_target)} items)")
                emit({"kind": "edge", "from": name, "out": out_port,
                      "to": target, "in": dst_in, "items": len(items_for_target)})
                queue.append((target, dst_in, items_for_target))

        print("\n=== done ===")
        emit({"kind": "done"})
        return results


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    nodes_dir = os.path.join(here, "nodes")
    engine = Engine(nodes_dir)

    print("=" * 44)
    print("  dugs — engine")
    print("=" * 44)
    print("discovered nodes:")
    for t, c in sorted(engine.registry.items()):
        print(f"  {t:22s}  {c.TITLE}  [{c.CATEGORY}]")

    wf_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "demo_workflow.json")
    print(f"\nrunning: {wf_path}\n")
    with open(wf_path) as f:
        workflow = json.load(f)
    engine.run_workflow(workflow)
