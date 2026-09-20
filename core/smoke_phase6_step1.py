# -*- coding: utf-8 -*-
"""阶段 6 · 步骤 1：轨迹偏差度量验收。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.schemas import TaskSpec
    from core.trajectory_metrics import compute_trajectory_deviation, normalize_trajectory

    sim = [
        {"t": 0, "joint_positions": [0.0, 0.0]},
        {"t": 1, "joint_positions": [0.5, -0.2]},
        {"t": 2, "joint_positions": [0.8, -0.4]},
    ]
    real = [
        {"t": 0, "joint_positions": [0.0, 0.0]},
        {"t": 1, "joint_positions": [0.55, -0.25]},
        {"t": 2, "joint_positions": [0.9, -0.5]},
    ]
    dev = compute_trajectory_deviation(sim, real)
    assert dev["ok"] is True
    assert dev["aligned_frames"] == 3
    assert isinstance(dev["mae"], float) and dev["mae"] > 0
    assert isinstance(dev["rmse"], float) and dev["rmse"] > 0

    # 空轨迹
    empty = compute_trajectory_deviation([], real)
    assert empty["ok"] is False

    # 脏数据可清洗
    dirty = normalize_trajectory([{"t": "1", "joint_positions": ["0.1", 2]}, "bad", {"joint_positions": [1]}])
    assert len(dirty) == 2

    # 不出现 ROS/厂商字段依赖
    src = (_ROOT / "core/trajectory_metrics.py").read_text(encoding="utf-8")
    assert "rclpy" not in src and "mujoco" not in src.lower()

    assert set(TaskSpec(task_id="a", action="m").to_dict()) == {
        "task_id",
        "action",
        "target",
        "constraints",
        "params",
        "source",
        "raw_text",
        "steps",
    }
    print("SMOKE_PHASE6_STEP1_OK", "mae", round(float(dev["mae"]), 4), "rmse", round(float(dev["rmse"]), 4))


if __name__ == "__main__":
    main()
