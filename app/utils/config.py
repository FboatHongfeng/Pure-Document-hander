"""用户配置管理 — 存储到用户 AppData 目录，不混入程序目录"""
import os
import sys
import json
from pathlib import Path


def _get_config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    return Path(base) / "Pure"


class Config:
    def __init__(self):
        self._dir = _get_config_dir()
        self._file = self._dir / "user_settings.json"
        self._data: dict = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data = self._read_json(self._file)
        self._loaded = True

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def get(self, key: str, default=None):
        self._ensure_loaded()
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._ensure_loaded()
        self._data[key] = value

    def save(self):
        self._ensure_loaded()
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    @property
    def path(self) -> Path:
        self._ensure_loaded()
        return self._file


config = Config()
