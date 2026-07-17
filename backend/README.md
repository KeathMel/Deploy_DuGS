# dugs-api (backend)

This folder is the whole server side of DuGS, split out from the desktop UI
so it can be built and run as its own container. It's still pure Python
standard library — no dependencies to install.

Contents: `api.py` (HTTP server + entry point), `engine.py` (runs workflows),
`node_base.py` / `device_base.py` (node contracts), `codegen.py` (servo →
Arduino code generation), `storage.py` (reads/writes Projects/Tabels/
Credentials as JSON), `tabel_store.py` (shared by the `data.tabel` node),
and `nodes/` (all node types).

## Run it directly (no container)

```bash
python3 api.py                      # http://127.0.0.1:5800, data next to this folder
python3 api.py 0.0.0.0 5800         # listen on all interfaces
```

Or via environment variables (same thing the container uses):

```bash
DUGS_API_HOST=0.0.0.0 DUGS_API_PORT=5800 DUGS_DATA_DIR=/path/to/data python3 api.py
```

## Run it in a container

```bash
docker compose up -d --build
```

This builds the image, starts it listening on `0.0.0.0:5800` inside the
container (mapped to `localhost:5800` on your machine), and persists
Projects/Tabels/Credentials in a named volume (`dugs_data`) so they survive
rebuilds/restarts.

Or without compose:

```bash
docker build -t dugs-api .
docker run -d -p 5800:5800 -v dugs_data:/data --name dugs-api dugs-api
```

Check it's alive:

```bash
curl http://localhost:5800/health
```

## Pointing the desktop UI at a containerized API

The UI reads the API's base URL from `theme.py`'s `API` constant, which now
falls back to an environment variable:

```bash
DUGS_API_URL=http://your-server:5800 python3 ui.py
```

## Important: this only separates the *workflow-running* half

Right now the desktop UI's Home screen (Projects/Tabels/Credentials
browsing, rename/duplicate/delete, etc.) reads and writes those JSON files
**directly off local disk** via its own copy of `storage.py` — it does not
go through this API. That's fine as long as the UI and the API container
share a filesystem (e.g. mount the same volume the container uses), but it
means the UI and the containerized API aren't *fully* decoupled yet: if you
run the API on a different machine than the UI, the Home screen won't see
what's on the server.

The clean fix is to add CRUD endpoints here (`GET/POST/DELETE /projects`,
`/tabels`, `/credentials`) and switch the UI's Home screen and Tabel Editor
to call those over HTTP instead of touching local files — full client/server
separation. That's a bigger change (touches `home_screen.py`,
`tabel_editor.py`, and this `storage.py`), so I held off doing it until you
confirm you want it. Say the word and I'll wire it up.
