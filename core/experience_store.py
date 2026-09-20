# -*- coding: utf-8 -*-
"""
轻量经验库（阶段 4 + 第 10 期 model 标签）。

存储：
- 新：experience/<action>__<target>__<model_slug>.json
- 旧：experience/<action>__<target>.json（只读兼容）

不是强化学习，只做记录与回放建议。默认禁止跨臂复用。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings

# 视为「默认臂族」：可兼容命中无 model_ref 的旧经验文件
_DEFAULT_MODEL_FAMILY = frozenset({"", "default", "builtin", "builtin_arm2"})


def _ensure_dir() -> Path:
    path = Path(settings.EXPERIENCE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def model_slug(model_ref: str | None = None) -> str:
    """把 model_ref 收成文件名安全片段。"""
    raw = str(model_ref if model_ref is not None else "default").strip() or "default"
    # 路径只取最后一段，避免盘符进键名
    raw = raw.replace("\\", "/").split("/")[-1]
    slug = re.sub(r"[^\w\-]+", "_", raw.lower()).strip("_") or "default"
    return slug[:64]


def is_default_model_family(model_ref: str | None) -> bool:
    """是否属于默认/内置臂族（可兼容旧无标签经验）。"""
    slug = model_slug(model_ref)
    if slug in _DEFAULT_MODEL_FAMILY:
        return True
    if slug.startswith("builtin"):
        return True
    return False


def allow_cross_model() -> bool:
    try:
        from config.safe import setting

        raw = setting("EXPERIENCE_ALLOW_CROSS_MODEL", False)
    except Exception:
        raw = getattr(settings, "EXPERIENCE_ALLOW_CROSS_MODEL", False)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def make_key(action: str, target: str = "", model_ref: str | None = None, *, with_model: bool = True) -> str:
    a = re.sub(r"[^\w\-]+", "_", (action or "unknown").strip().lower()) or "unknown"
    t = re.sub(r"[^\w\-]+", "_", (target or "none").strip().lower()) or "none"
    base = f"{a}__{t}"
    if not with_model:
        return base
    return f"{base}__{model_slug(model_ref)}"


def _path_tagged(action: str, target: str = "", model_ref: str | None = None) -> Path:
    return _ensure_dir() / f"{make_key(action, target, model_ref, with_model=True)}.json"


def _path_legacy(action: str, target: str = "") -> Path:
    return _ensure_dir() / f"{make_key(action, target, with_model=False)}.json"


def _load_ok(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not data.get("ok"):
        return None
    return data


def _annotate(data: dict[str, Any], *, source: str) -> dict[str, Any]:
    out = dict(data)
    out["_experience_source"] = source  # tagged | legacy | cross
    if source == "legacy" and not out.get("model_ref"):
        out["_legacy_untagged"] = True
    return out


def find_experience(
    action: str,
    target: str = "",
    model_ref: str | None = None,
) -> dict[str, Any] | None:
    """
    查找成功经验。
    - 优先同 model 标签文件
    - 默认臂族可回退旧无标签文件
    - EXPERIENCE_ALLOW_CROSS_MODEL=true 时可跨标签/旧文件（调试用，默认关）
    """
    tagged = _load_ok(_path_tagged(action, target, model_ref))
    if tagged is not None:
        return _annotate(tagged, source="tagged")

    # 旧文件兼容
    legacy = _load_ok(_path_legacy(action, target))
    if legacy is not None:
        legacy_model = legacy.get("model_ref")
        can_use_legacy = allow_cross_model() or is_default_model_family(model_ref)
        if can_use_legacy:
            # 旧记录若已写了非默认 model_ref，且当前不同键，则不命中
            if (
                legacy_model
                and not is_default_model_family(str(legacy_model))
                and not allow_cross_model()
                and model_slug(str(legacy_model)) != model_slug(model_ref)
            ):
                pass
            else:
                return _annotate(legacy, source="legacy")

    if not allow_cross_model():
        return None

    # 跨臂调试：同 action+target 任意带标签成功文件（取最新）
    prefix = make_key(action, target, with_model=False) + "__"
    root = _ensure_dir()
    candidates: list[Path] = sorted(
        [p for p in root.glob(f"{prefix}*.json")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        data = _load_ok(path)
        if data is not None:
            return _annotate(data, source="cross")
    return None


def remember_experience(
    *,
    action: str,
    target: str,
    raw_text: str,
    trajectory: list[dict[str, Any]],
    ok: bool,
    reason: str = "",
    params: dict[str, Any] | None = None,
    model_ref: str | None = None,
) -> dict[str, Any]:
    """写入/更新一条经验（写入带 model 标签的新键；不删旧文件）。"""
    params = dict(params or {})
    # params 内 model_ref 可作缺省
    resolved = model_ref if model_ref is not None else params.get("model_ref")
    resolved = str(resolved or "default")
    path = _path_tagged(action, target, resolved)

    suggested: list[float] = []
    if trajectory:
        last = trajectory[-1]
        jp = last.get("joint_positions") or []
        suggested = [float(x) for x in jp]

    record = {
        "key": make_key(action, target, resolved, with_model=True),
        "action": action,
        "target": target,
        "model_ref": resolved,
        "ok": ok,
        "reason": reason,
        "raw_text": raw_text,
        "params": params,
        "suggested_joint_targets": suggested,
        "trajectory_frames": len(trajectory),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "use_count": 0,
    }

    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if ok:
                record["use_count"] = int(old.get("use_count") or 0)
            elif old.get("ok"):
                # 不覆盖已有成功经验
                return old
        except Exception:
            pass

    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def mark_experience_used(action: str, target: str = "", model_ref: str | None = None) -> None:
    """增加复用次数；优先标签文件，其次在允许时点旧文件。"""
    path = _path_tagged(action, target, model_ref)
    if not path.exists():
        # 命中的可能是 legacy：仅默认族或跨臂开关时更新旧文件
        if allow_cross_model() or is_default_model_family(model_ref):
            path = _path_legacy(action, target)
        else:
            return
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["use_count"] = int(data.get("use_count") or 0) + 1
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def list_experiences(limit: int = 20) -> list[dict[str, Any]]:
    """列出经验摘要；字段只增不减，兼容旧 json。"""
    root = _ensure_dir()
    files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[: max(1, limit)]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = str(data.get("raw_text") or "")
            out.append(
                {
                    "key": data.get("key", path.stem),
                    "action": data.get("action"),
                    "target": data.get("target"),
                    "model_ref": data.get("model_ref") or "-",
                    "ok": data.get("ok"),
                    "use_count": data.get("use_count", 0),
                    "updated_at": data.get("updated_at"),
                    "trajectory_frames": data.get("trajectory_frames"),
                    "raw_text": raw[:48] + ("..." if len(raw) > 48 else ""),
                }
            )
        except Exception:
            continue
    return out


# 兼容旧导入路径；实现见 core.browse_tables
def experiences_table_rows(limit: int = 20) -> list[dict[str, Any]]:
    from core.browse_tables import experiences_table_rows as _rows

    return _rows(limit)
