# -*- coding: utf-8 -*-
"""
安全读取配置（对抗 Streamlit 热重载导致的 settings 半旧缓存）。
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any


def fresh_settings() -> ModuleType:
    """重新加载 config.settings，并写回 config 包引用。"""
    import config
    import config.settings as settings_mod

    settings_mod = importlib.reload(settings_mod)
    config.settings = settings_mod
    return settings_mod


def setting(name: str, default: Any = None) -> Any:
    """按名读取配置；缺失时 reload 一次，仍无则返回 default。"""
    import config.settings as settings_mod

    if hasattr(settings_mod, name):
        return getattr(settings_mod, name)
    settings_mod = fresh_settings()
    return getattr(settings_mod, name, default)
