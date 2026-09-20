# -*- coding: utf-8 -*-
"""
一次演示包导出（第 10 期 · 步骤 4）

把单条实验打成可拷贝的 zip：任务单摘要 + 轨迹摘要 + 运行快照 + 人话说明。
脱敏：不写入 API Key / 含 sk- 的字段。
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings
from core.run_snapshot import snapshot_contains_secrets

_SECRET_KEY_MARKERS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
    "authorization",
    "private_key",
    "access_key",
)


def packs_dir() -> Path:
    root = Path(getattr(settings, "EXPERIMENTS_DIR", "experiments"))
    path = root / "packs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_experiment_by_id(experiment_id: str) -> dict[str, Any] | None:
    """从 experiments/<id>.json 读取；不存在返回 None。"""
    exp_id = str(experiment_id or "").strip()
    if not exp_id:
        return None
    # 防止路径穿越
    if re.search(r"[\\/]", exp_id) or ".." in exp_id:
        return None
    path = Path(settings.EXPERIMENTS_DIR) / f"{exp_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def resolve_experiment_id(experiment_id: str | None = None, *, latest: bool = False) -> str | None:
    """指定 id，或 latest=True 取最近一条。"""
    if experiment_id and str(experiment_id).strip():
        return str(experiment_id).strip()
    if not latest:
        return None
    from core.experiment_store import list_recent_experiments

    rows = list_recent_experiments(1)
    if not rows:
        return None
    return str(rows[0].get("experiment_id") or "") or None


def _is_secret_key(name: str) -> bool:
    low = str(name or "").strip().lower().replace("-", "_")
    return any(m in low for m in _SECRET_KEY_MARKERS)


def redact_for_export(obj: Any) -> Any:
    """递归脱敏：去掉密钥键与 sk- 字符串值。"""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if _is_secret_key(str(k)):
                continue
            if isinstance(v, str) and "sk-" in v.lower():
                continue
            out[str(k)] = redact_for_export(v)
        return out
    if isinstance(obj, list):
        return [redact_for_export(x) for x in obj]
    return obj


def build_trajectory_summary(sim_result: dict[str, Any] | None) -> dict[str, Any]:
    """轨迹摘要：帧数 + 首末关节，不塞全量轨迹。"""
    sim = sim_result or {}
    traj = list(sim.get("trajectory") or [])
    first_jp: list[float] = []
    last_jp: list[float] = []
    if traj:
        first_jp = [float(x) for x in (traj[0].get("joint_positions") or [])]
        last_jp = [float(x) for x in (traj[-1].get("joint_positions") or [])]
    return {
        "frames": len(traj),
        "first_joint_positions": first_jp,
        "last_joint_positions": last_jp,
        "metrics": dict(sim.get("metrics") or {}),
        "engine_name": sim.get("engine_name"),
        "message": sim.get("message"),
        "note": "完整逐帧轨迹见原实验 JSON；演示包只保留首末摘要以便拷贝。",
    }


def build_readme(record: dict[str, Any]) -> str:
    spec = record.get("task_spec") or {}
    snap = record.get("run_snapshot") or {}
    lines = [
        "RobeWhisper 一次演示包说明",
        "========================",
        "",
        "这是什么",
        "--------",
        "本压缩包记录「某一条自然语言试机」的可复述证据：任务单、轨迹摘要、运行环境快照。",
        "用于答辩拷贝、复盘配置，不是工业抓取合格证。",
        "",
        "包内文件",
        "--------",
        "- experiment.json：脱敏后的实验记录（轨迹已改为指向摘要）",
        "- trajectory_summary.json：帧数与首末关节角",
        "- run_snapshot.json：引擎/LLM/机器人后端与非机密配置",
        "- README_演示说明.txt：本说明",
        "",
        "本次摘要",
        "--------",
        f"- experiment_id: {record.get('experiment_id')}",
        f"- 成功: {record.get('ok')}",
        f"- 动作/目标: {spec.get('action')} / {spec.get('target')}",
        f"- 原始指令: {record.get('raw_text')}",
        f"- 模型: {(snap.get('model_ref') if isinstance(snap, dict) else None) or '-'}",
        f"- 导出时间(UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "不能说明什么",
        "------------",
        "- 不能证明现实机械臂已抓住物体",
        "- 不能证明仿真物理与真机完全一致",
        "- 若含 RSR 且对照为 pseudo_real，只是软件演示，不是真机回流闭环",
        "- 不含 API Key；若需复现 api 解析，请在本机自行配置 .env",
        "",
        "如何复现（本机）",
        "----------------",
        "1. 对照 run_snapshot.json 中的 backends / flags",
        "2. 启动网站后输入相近自然语言指令",
        "3. 经验按 model_ref 分区，换臂不会默默复用另一臂的经验",
        "",
    ]
    return "\n".join(lines)


def prepare_pack_files(record: dict[str, Any]) -> dict[str, str]:
    """
    生成包内各文件文本内容（已脱敏）。
    返回文件名 -> 文本。
    """
    safe = redact_for_export(record)
    if not isinstance(safe, dict):
        safe = {}

    # 实验 JSON：去掉全量轨迹，减小体积并避免误当「全证据」
    sim = dict(safe.get("sim_result") or {})
    summary = build_trajectory_summary(record.get("sim_result") or {})
    if "trajectory" in sim:
        sim["trajectory"] = []
        sim["trajectory_note"] = "已省略全量轨迹；请看 trajectory_summary.json"
    safe["sim_result"] = sim

    snap = safe.get("run_snapshot")
    if not isinstance(snap, dict) or not snap:
        snap = {
            "schema_version": 1,
            "note": "原实验无 run_snapshot（旧记录）；请以 adapters 字段为参考",
            "adapters": safe.get("adapters") or {},
        }
        safe["run_snapshot"] = snap

    files = {
        "experiment.json": json.dumps(safe, ensure_ascii=False, indent=2),
        "trajectory_summary.json": json.dumps(summary, ensure_ascii=False, indent=2),
        "run_snapshot.json": json.dumps(snap, ensure_ascii=False, indent=2),
        "README_演示说明.txt": build_readme(record if isinstance(record, dict) else safe),
    }
    return files


def export_demo_pack(
    experiment_id: str | None = None,
    *,
    latest: bool = False,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """
    导出 zip 演示包。

    返回：
      ok, experiment_id, zip_path, message, files(list)
    """
    exp_id = resolve_experiment_id(experiment_id, latest=latest)
    if not exp_id:
        return {
            "ok": False,
            "experiment_id": "",
            "zip_path": "",
            "message": "没有可导出的实验。请先成功跑一条指令，或指定 experiment_id。",
            "files": [],
        }
    record = load_experiment_by_id(exp_id)
    if record is None:
        return {
            "ok": False,
            "experiment_id": exp_id,
            "zip_path": "",
            "message": f"找不到实验文件：{exp_id}.json",
            "files": [],
        }

    files = prepare_pack_files(record)
    # 导出前再扫一遍密钥
    for name, text in files.items():
        if name.endswith(".json"):
            try:
                hits = snapshot_contains_secrets(json.loads(text))
            except Exception:
                hits = []
            if hits or "sk-" in text.lower():
                return {
                    "ok": False,
                    "experiment_id": exp_id,
                    "zip_path": "",
                    "message": f"脱敏失败，拒绝导出（可疑字段于 {name}）",
                    "files": [],
                }

    dest_root = Path(out_dir) if out_dir is not None else packs_dir()
    dest_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = dest_root / f"demo_pack_{exp_id}_{stamp}.zip"

    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, text in files.items():
                zf.writestr(name, text.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "experiment_id": exp_id,
            "zip_path": "",
            "message": f"打包失败：{exc}",
            "files": list(files.keys()),
        }

    return {
        "ok": True,
        "experiment_id": exp_id,
        "zip_path": str(zip_path.resolve()),
        "message": f"演示包已生成：{zip_path.name}",
        "files": list(files.keys()),
    }
