"""
storage.py — local filesystem read/write for projects (workflows) and tabels
(spreadsheets). Pure file I/O, no Qt imports here on purpose.
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(HERE, "projects")
TABELS_DIR = os.path.join(HERE, "tabels")
CREDENTIALS_DIR = os.path.join(HERE, "credentials")
MEMORY_DIR = os.path.join(HERE, "memory_banks")
DOWNLOADS = os.path.expanduser("~/Downloads")


def _ensure(d):
    os.makedirs(d, exist_ok=True)


def _list(d):
    _ensure(d)
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


def _path(d, name):
    return os.path.join(d, f"{name}.json")


def _load(d, name):
    with open(_path(d, name)) as f:
        return json.load(f)


def _save(d, name, data):
    _ensure(d)
    with open(_path(d, name), "w") as f:
        json.dump(data, f, indent=2)


def list_projects(): return _list(PROJECTS_DIR)
def load_project(n): return _load(PROJECTS_DIR, n)
def save_project(n, d): _save(PROJECTS_DIR, n, d)


# ---- project kind: "normal" (runs in the engine) or "servo" (generates
#      Arduino code instead of running). Stored in the project JSON.
def project_kind(n):
    """Return 'normal' or 'servo' for a saved project."""
    try:
        d = _load(PROJECTS_DIR, n)
        return d.get("kind", "normal")
    except Exception:
        return "normal"


# where generated .ino sketches get written
SKETCHES_DIR = os.path.join(HERE, "sketches")


def save_sketch(name, code):
    """Write a generated Arduino sketch. Arduino requires the .ino file to sit
    in a folder of the same name, so we make sketches/<name>/<name>.ino"""
    _ensure(SKETCHES_DIR)
    folder = os.path.join(SKETCHES_DIR, name)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}.ino")
    with open(path, "w") as f:
        f.write(code)
    return path


def list_tabels(): return _list(TABELS_DIR)
def load_tabel(n): return _load(TABELS_DIR, n)


def save_tabel(n, d):
    for i, row in enumerate(d.get("rows", []), start=1):
        row["id"] = i
    _save(TABELS_DIR, n, d)


# ---- credentials: named secrets (e.g. a DeepSeek token) reusable by nodes ----
def list_credentials(): return _list(CREDENTIALS_DIR)
def load_credential(n): return _load(CREDENTIALS_DIR, n)
def save_credential(n, d): _save(CREDENTIALS_DIR, n, d)


def delete_credential(n):
    p = _path(CREDENTIALS_DIR, n)
    if os.path.exists(p):
        os.remove(p)


# ---- UI layout state (panel sizes etc.), so the window remembers itself ----
_UI_STATE = os.path.join(HERE, "ui_state.json")


def load_ui_state():
    try:
        with open(_UI_STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_ui_state(d):
    try:
        with open(_UI_STATE, "w") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass


def new_tabel(n):
    save_tabel(n, {"name": n, "columns": ["column1"], "rows": []})


# ---- memory banks -------------------------------------------------------
# A memory bank is a small key/value store the AI/workflow can save things
# into, like a Tabel but simpler: each key holds a value plus optional
# expiry. Stored as plain JSON files so it works anywhere, no database.
import time as _time


def list_memory_banks():
    return _list(MEMORY_DIR)


def load_memory_bank(n):
    try:
        return _load(MEMORY_DIR, n)
    except Exception:
        return {"name": n, "entries": {}}


def save_memory_bank(n, d):
    _ensure(MEMORY_DIR)
    _save(MEMORY_DIR, n, d)


def new_memory_bank(n):
    save_memory_bank(n, {"name": n, "entries": {}})


def delete_memory_bank(n):
    try:
        os.remove(_path(MEMORY_DIR, n))
    except Exception:
        pass


def _bank_alive(entry):
    """An entry is alive if it has no expiry, or its expiry is still ahead."""
    exp = entry.get("expires_at")
    return exp is None or exp > _time.time()


def memory_get(bank, key):
    """Read one key, honouring expiry. Returns None if missing or expired."""
    d = load_memory_bank(bank)
    entry = (d.get("entries") or {}).get(key)
    if entry is None or not _bank_alive(entry):
        return None
    return entry.get("value")


def memory_all(bank):
    """Every live key/value in the bank, dropping expired ones as we go."""
    d = load_memory_bank(bank)
    entries = d.get("entries") or {}
    out, changed = {}, False
    for k, e in list(entries.items()):
        if _bank_alive(e):
            out[k] = e.get("value")
        else:
            del entries[k]; changed = True
    if changed:
        save_memory_bank(bank, d)
    return out


def memory_set(bank, key, value, ttl_seconds=None, append=False):
    """Write a key. ttl_seconds=None means it never expires. append=True keeps
    the old value and adds to it (list or string) instead of overwriting."""
    d = load_memory_bank(bank)
    entries = d.setdefault("entries", {})
    expires = (_time.time() + ttl_seconds) if ttl_seconds else None
    if append and key in entries and _bank_alive(entries[key]):
        old = entries[key].get("value")
        if isinstance(old, list):
            value = old + (value if isinstance(value, list) else [value])
        else:
            value = f"{old}\n{value}"
    entries[key] = {"value": value, "expires_at": expires,
                    "updated_at": _time.time()}
    save_memory_bank(bank, d)
    return value
