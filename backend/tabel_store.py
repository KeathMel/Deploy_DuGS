import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
TABELS_DIR = os.path.join(HERE, "tabels")


def ensure_dir():
    os.makedirs(TABELS_DIR, exist_ok=True)

def tabel_path(name):
    return os.path.join(TABELS_DIR, f"{name}.json")

def list_tabels():
    ensure_dir()
    return sorted(f[:-5] for f in os.listdir(TABELS_DIR) if f.endswith(".json"))

def load_tabel(name):
    with open(tabel_path(name)) as f:
        return json.load(f)

def save_tabel(name, data):
    ensure_dir()
    for i, row in enumerate(data.get("rows", []), start=1):
        row["id"] = i
    with open(tabel_path(name), "w") as f:
        json.dump(data, f, indent=2)

def new_tabel(name):
    data = {"name": name, "columns": ["column1"], "rows": []}
    save_tabel(name, data)
    return data
