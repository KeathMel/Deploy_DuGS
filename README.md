# DuGS Runner

This is the half of DuGS that just runs workflows. No GUI, no editor, no Qt.
You build workflows in the DuGS app on your own machine, then drop them here and
this keeps them running — on a Pi, a server, a phone, whatever you leave on.

If you want to BUILD workflows you want the app instead:
https://github.com/KeathMel/DuGS

---

## WHAT IT DOES

It reads your workflows and does whatever each one's own trigger says.

| Trigger in your workflow | What the runner does |
|---|---|
| Webhook | listens on that path and fires when something hits it |
| Schedule | fires on its interval, or at its daily time |
| Manual | sits there until you ask it to run |

Nothing to configure twice. The workflow already says how it should fire.

---

## INSTALL

Everything it needs ships with it. Python 3.9 or higher, nothing to pip install.

```
git clone https://github.com/KeathMel/DuGS_Runner.git
cd DuGS_Runner
python3 dugs_runner.py
```

That's it. It runs anywhere Python runs — including a phone under Termux.

---

## USING IT

Two ways to get a workflow in here:

**From the app** — hit the Deploy button, type this runner's address. It lands
here and starts running straight away, no restart.

**By hand** — drop the .json into `projects/`. The runner notices within a few
seconds and picks it up on its own.

```
python3 dugs_runner.py                    # run everything on its triggers
python3 dugs_runner.py --list             # what's loaded and how it fires
python3 dugs_runner.py --run my_workflow  # run one right now
python3 dugs_runner.py --port 8080        # different port
```

While it's running:

```
curl http://localhost:5800/health         # is it alive
curl http://localhost:5800/workflows      # what's loaded
curl -X POST http://localhost:5800/run/my_workflow    # run one over http
curl -X POST http://localhost:5800/deploy -d @wf.json # send a workflow in
```

Webhook workflows answer on whatever path you gave them in the app.

---

## CONTAINER

```
docker compose up -d
docker compose logs -f
```

Your workflows are mounted from `./projects`, so dropping a file in on your
machine puts it inside the container too — no container paths to work out, and
no rebuild. The runner notices and picks it up by itself.

Without compose:

```
docker build -t dugs-runner .
docker run -d -p 5800:5800 -v ./projects:/data/projects --name dugs dugs-runner
```

---

## ADDING A NODE

Same as the app: drop a `.py` file in `nodes/` and restart. It has to be a node
the app has too, or the workflow won't load there.

If you add nodes to your DuGS app, copy them here as well so both sides know the
same node types.

---

## WHATS IN HERE

| File | What it does |
|---|---|
| `dugs_runner.py` | The runner. Reads workflows, watches their triggers, fires them. |
| `engine.py` | Walks the graph and runs the nodes. Same engine the app uses. |
| `node_base.py` | The base class every node builds on, plus `{{ }}` expressions. |
| `storage.py` | Reads and writes projects, tabels, credentials, memory banks. |
| `tabel_store.py` | Storage for tabels. |
| `ai_helper.py` | Shared AI token counter, used by the AI and Memory nodes. |
| `nodes/` | Every node that can run. No robotics nodes — those generate Arduino code and don't run here. |
| `projects/` | Your workflows. |

---

## WHAT IT DOESNT DO

No editor. Robotics/servo projects are skipped, since those generate Arduino
code rather than running. Build those in the app and flash the board.
