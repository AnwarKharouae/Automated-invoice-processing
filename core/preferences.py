import os
import json
from core.paths import resource_path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PREFS_FILE = resource_path("preferences.json")

DEFAULTS = {
    "excel_export_dir": os.path.join(os.path.expanduser("~"), "Desktop"),
    "session_save_dir": os.path.join(os.path.expanduser("~"), "Desktop"),
}


def load_preferences():
    if not os.path.exists(PREFS_FILE):
        return dict(DEFAULTS)
    try:
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = dict(DEFAULTS)
        out.update(data)
        return out
    except Exception:
        return dict(DEFAULTS)


def save_preferences(prefs):
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)