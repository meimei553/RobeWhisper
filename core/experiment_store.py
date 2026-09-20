# -*- coding: utf-8 -*-
"""
虚拟实验数据导出（阶段 4 + 第 10 期快照）。

每次 Pipeline 执行可落盘 JSON；并追加一行到 summary.csv。
不修改 TaskSpec 主字段；run_snapshot 为旁路字段（只增）。
"""

from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


def _ensure_dir() -> Path:
    path = Path(settings.EXPERIMENTS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_run_snapshot(
    *,
    run_snapshot: dict[str, Any] | None,
    adapters: dict[str, Any] | None,
    model_ref: str | None,
    llm: Any = None,
    engine: Any = None,
    robot: Any = None,
    snapshot_extra: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """若未显式传入快照则自动采集；采集失败返回 None（不挡落盘）。"""
    if isinstance(run_snapshot, dict) and run_snapshot:
        return run_snapshot
    try:
        from core.run_snapshot import collect_run_snapshot

        return collect_run_snapshot(
            adapters=adapters,
            llm=llm,
            engine=engine,
            robot=robot,
            model_ref=model_ref,
            extra=snapshot_extra,
        )
    except Exception:
        return None


def build_experiment_record(
    *,
    raw_text: str,
    task_spec: dict[str, Any] | None,
    sim_result: dict[str, Any] | None,
    ok: bool,
    code: str = "OK",
    message: str = "",
    adapters: dict[str, Any] | None = None,
    experience_hit: bool = False,
    run_snapshot: dict[str, Any] | None = None,
    model_ref: str | None = None,
    llm: Any = None,
    engine: Any = None,
    robot: Any = None,
    snapshot_extra: dict[str, Any] | None = None,
    robot_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    组装一条实验记录（内存对象）。

    run_snapshot：第 10 期旁路字段；未传则尝试自动采集（不含密钥）。
    robot_result：第 11 期旁路；真机成败摘要（endpoint 已脱敏）。
    """
    sim = sim_result or {}
    metrics = dict(sim.get("metrics") or {})
    traj = list(sim.get("trajectory") or [])
    metrics.setdefault("frames", len(traj))
    metrics.setdefault("success", 1.0 if ok else 0.0)

    # model_ref：参数 > task_spec.params > default
    spec = task_spec or {}
    params = spec.get("params") if isinstance(spec, dict) else {}
    params = params if isinstance(params, dict) else {}
    resolved_model = str(model_ref or params.get("model_ref") or "default")

    snap = _resolve_run_snapshot(
        run_snapshot=run_snapshot,
        adapters=adapters,
        model_ref=resolved_model,
        llm=llm,
        engine=engine,
        robot=robot,
        snapshot_extra=snapshot_extra,
    )

    record: dict[str, Any] = {
        "experiment_id": uuid.uuid4().hex[:16],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_text": raw_text,
        "ok": ok,
        "code": code,
        "message": message,
        "task_spec": task_spec or {},
        "sim_result": sim,
        "metrics": metrics,
        "adapters": adapters or {},
        "experience_hit": experience_hit,
    }
    if snap is not None:
        record["run_snapshot"] = snap

    # 真机旁路：只增不改 TaskSpec
    if robot_result is not None:
        try:
            from core.robot_bridge_contract import sanitize_robot_result_for_store

            cleaned = sanitize_robot_result_for_store(
                robot_result if isinstance(robot_result, dict) else None
            )
            if cleaned is not None:
                record["robot_result"] = cleaned
        except Exception:
            if isinstance(robot_result, dict):
                record["robot_result"] = robot_result

    return record


def save_experiment(record: dict[str, Any]) -> dict[str, str]:
    """
    写入 experiments/<id>.json，并追加 summary.csv。

    返回 {ok, path, experiment_id, message}
    注意：summary.csv 表头保持阶段4字段，避免旧文件追加错列；
    引擎/模型等信息只在 JSON 与浏览表中展示。
    """
    try:
        root = _ensure_dir()
        exp_id = str(record.get("experiment_id") or uuid.uuid4().hex[:16])
        record["experiment_id"] = exp_id
        json_path = root / f"{exp_id}.json"
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        csv_path = root / "summary.csv"
        write_header = not csv_path.exists()
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "experiment_id",
                    "created_at",
                    "ok",
                    "action",
                    "target",
                    "frames",
                    "experience_hit",
                    "message",
                ],
            )
            if write_header:
                writer.writeheader()
            spec = record.get("task_spec") or {}
            metrics = record.get("metrics") or {}
            writer.writerow(
                {
                    "experiment_id": exp_id,
                    "created_at": record.get("created_at", ""),
                    "ok": record.get("ok", False),
                    "action": spec.get("action", ""),
                    "target": spec.get("target", ""),
                    "frames": metrics.get("frames", 0),
                    "experience_hit": record.get("experience_hit", False),
                    "message": (record.get("message") or "")[:120],
                }
            )
        return {
            "ok": "true",
            "path": str(json_path),
            "experiment_id": exp_id,
            "message": f"实验已保存: {json_path.name}",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": "false", "path": "", "experiment_id": "", "message": str(exc)}


def list_recent_experiments(limit: int = 10) -> list[dict[str, Any]]:
    """读取最近实验摘要（从 json 文件；字段只增不减，兼容旧记录）。"""
    root = _ensure_dir()
    files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[: max(1, limit)]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            spec = data.get("task_spec") or {}
            metrics = data.get("metrics") or {}
            rsr = data.get("rsr")
            has_rsr = isinstance(rsr, dict) and bool(rsr) and not rsr.get("skipped")
            mae = None
            if isinstance(rsr, dict):
                mae = (rsr.get("deviation") or {}).get("mae")
            raw = str(data.get("raw_text") or "")
            snap = data.get("run_snapshot") if isinstance(data.get("run_snapshot"), dict) else {}
            adapters_snap = (snap.get("adapters") or {}) if snap else {}
            engine_info = adapters_snap.get("engine") if isinstance(adapters_snap, dict) else {}
            engine_name = ""
            if isinstance(engine_info, dict):
                engine_name = str(engine_info.get("name") or "")
            if not engine_name:
                ad = data.get("adapters") or {}
                if isinstance(ad, dict):
                    engine_name = str(ad.get("engine") or "")
            model_ref = ""
            if snap:
                model_ref = str(snap.get("model_ref") or "")
            if not model_ref:
                model_ref = str((spec.get("params") or {}).get("model_ref") or "")
            out.append(
                {
                    "experiment_id": data.get("experiment_id", path.stem),
                    "ok": data.get("ok"),
                    "action": spec.get("action"),
                    "target": spec.get("target"),
                    "created_at": data.get("created_at"),
                    "experience_hit": data.get("experience_hit"),
                    "frames": metrics.get("frames"),
                    "has_rsr": has_rsr,
                    "rsr_mae": mae,
                    "grasp_proxy": metrics.get("grasp_proxy") or "-",
                    "pose_source": (
                        (snap.get("extra") or {}).get("pose_source")
                        if isinstance(snap.get("extra"), dict)
                        else None
                    )
                    or snap.get("pose_source")
                    or metrics.get("pose_source")
                    or "-",
                    "raw_text": raw[:48] + ("..." if len(raw) > 48 else ""),
                    "engine": engine_name or "-",
                    "model_ref": model_ref or "-",
                    "has_run_snapshot": bool(snap),
                    "has_robot_result": isinstance(data.get("robot_result"), dict),
                }
            )
        except Exception:
            continue
    return out


# 兼容旧导入路径；实现见 core.browse_tables
def experiments_table_rows(limit: int = 10) -> list[dict[str, Any]]:
    from core.browse_tables import experiments_table_rows as _rows

    return _rows(limit)
