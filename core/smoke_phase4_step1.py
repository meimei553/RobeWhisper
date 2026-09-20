# -*- coding: utf-8 -*-
"""阶段4·步骤1：仅验收实验导出（不测经验/Pipeline）。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from config import settings
    from core.experiment_store import build_experiment_record, list_recent_experiments, save_experiment
    from core.schemas import TaskSpec

    rec = build_experiment_record(
        raw_text="测试导出",
        task_spec={"action": "move", "target": ""},
        sim_result={"ok": True, "trajectory": [{"t": 0, "joint_positions": [0.0]}], "metrics": {}},
        ok=True,
        message="step1",
    )
    saved = save_experiment(rec)
    assert saved["ok"] == "true", saved
    path = Path(saved["path"])
    assert path.exists()
    assert (Path(settings.EXPERIMENTS_DIR) / "summary.csv").exists()
    assert list_recent_experiments(3)

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
    print("SMOKE_PHASE4_STEP1_OK", saved["experiment_id"])


if __name__ == "__main__":
    main()
