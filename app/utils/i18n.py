"""JSON文本加载器"""
import json
import os

_current_lang = "zh_CN"
_cache: dict = {}


def _get_i18n_dir() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "resources", "i18n")


def load_texts(lang: str | None = None) -> dict:
    """加载指定语言的文本字典，结果会被缓存"""
    global _current_lang
    if lang:
        _current_lang = lang
    if _current_lang in _cache:
        return _cache[_current_lang]
    path = os.path.join(_get_i18n_dir(), f"{_current_lang}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache[_current_lang] = data
    return data


def t(*keys: str) -> str:
    """通过点号分隔的 key 获取文本，如 t('convert', 'title')"""
    data = load_texts()
    for k in keys:
        data = data.get(k, {})
    if not isinstance(data, str):
        return ".".join(keys)
    return data
