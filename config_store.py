import json
import os


def default_output_dir():
    return os.path.join(os.path.expanduser("~"), "Videos", "ClipAI")


def config_path():
    return os.path.join(os.path.expanduser("~"), ".ytclipper_web.json")


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        return {}
    return {}


def save_config(data):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        return

