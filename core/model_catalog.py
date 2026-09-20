# -*- coding: utf-8 -*-
"""
模型目录扫描与上传保存（阶段 2）。

只做文件系统与相对路径管理；真正加载仍走 BaseEngine.load。
"""

from __future__ import annotations

import re
from pathlib import Path

from config import settings

# 允许的模型后缀（阶段 2 以 MJCF/xml 为主）
ALLOWED_SUFFIXES = {".xml", ".mjcf"}


def _default_model_rel() -> str:
    """兼容热重载：避免 settings 旧缓存缺字段导致页面崩。"""
    return str(getattr(settings, "DEFAULT_MODEL_REL", "builtin_arm2/model.xml") or "builtin_arm2/model.xml")


def uploads_dir() -> Path:
    """上传目录：MODELS_DIR/uploads。"""
    path = settings.MODELS_DIR / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_rel_model_ref(path: Path) -> str:
    """转为相对 MODELS_DIR 的引用，供 engine.load 使用。"""
    path = path.resolve()
    root = settings.MODELS_DIR.resolve()
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        # 不在 MODELS_DIR 下时，仍返回绝对路径字符串（引擎可解析）
        return str(path)


def list_model_options() -> list[dict[str, str]]:
    """
    扫描 MODELS_DIR 下可用模型。

    返回 [{label, ref}, ...]，ref 为相对 MODELS_DIR 的路径或 default。
    """
    root = settings.MODELS_DIR
    root.mkdir(parents=True, exist_ok=True)
    default_rel = _default_model_rel()
    options: list[dict[str, str]] = [
        {"label": f"默认内置臂 ({default_rel})", "ref": "default"},
    ]

    seen: set[str] = {"default", default_rel.replace("\\", "/")}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        rel = to_rel_model_ref(path)
        if rel in seen:
            continue
        seen.add(rel)
        # 接触试机场景给人话标签，避免和默认臂混淆
        if "builtin_arm2_contact" in rel.replace("\\", "/").lower():
            label = f"接触试机场景（臂+方块）· {rel}"
        else:
            label = rel
        options.append({"label": label, "ref": rel})
    return options


def _safe_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE)
    if not name.lower().endswith((".xml", ".mjcf")):
        name = f"{name}.xml"
    return name or "upload.xml"


def save_uploaded_model(filename: str, data: bytes) -> dict[str, str]:
    """
    保存上传的模型文件到 uploads/。

    成功返回 {ok, ref, path, message}；失败 ok=false。
    """
    if not data:
        return {"ok": "false", "ref": "", "path": "", "message": "文件为空"}
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIXES:
        return {
            "ok": "false",
            "ref": "",
            "path": "",
            "message": "仅支持 .xml / .mjcf（MJCF）文件",
        }

    dest = uploads_dir() / _safe_filename(filename)
    dest.write_bytes(data)
    ref = to_rel_model_ref(dest)
    return {
        "ok": "true",
        "ref": ref,
        "path": str(dest),
        "message": f"已保存: {ref}",
    }
