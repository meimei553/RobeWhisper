# -*- coding: utf-8 -*-
"""阶段 7 · 步骤 3：实验/经验浏览增强验收。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from config import settings
    from core.browse_tables import experiences_table_rows, experiments_table_rows
    from core.experience_store import list_experiences, remember_experience
    from core.experiment_store import (
        build_experiment_record,
        list_recent_experiments,
        save_experiment,
    )

    # 写入一条带 rsr 的实验（不改存储主路径）
    rec = build_experiment_record(
        raw_text="步骤3浏览测试把红色杯子拿起来",
        task_spec={"action": "grab", "target": "red_cup"},
        sim_result={
            "ok": True,
            "trajectory": [{"t": 0, "joint_positions": [0.1, 0.2]}],
            "metrics": {},
        },
        ok=True,
        message="step3_browse",
        experience_hit=False,
    )
    rec["rsr"] = {
        "ok": True,
        "skipped": False,
        "reference_source": "pseudo_real",
        "deviation": {"mae": 0.12},
        "calibration": {"updated": True},
    }
    saved = save_experiment(rec)
    assert saved["ok"] == "true", saved
    assert Path(saved["path"]).exists()

    recent = list_recent_experiments(20)
    assert recent
    hit = next(x for x in recent if x.get("experiment_id") == saved["experiment_id"])
    assert hit.get("has_rsr") is True
    assert hit.get("rsr_mae") == 0.12
    assert "frames" in hit and "raw_text" in hit

    table = experiments_table_rows(20)
    assert table and "含RSR" in table[0]
    assert any(r.get("编号") == saved["experiment_id"] and r.get("含RSR") == "是" for r in table)

    # 经验库：旧字段仍在，新字段可读
    remember_experience(
        action="browse_test",
        target="cup",
        raw_text="经验浏览测试",
        trajectory=[{"t": 0, "joint_positions": [0.0]}],
        ok=True,
    )
    exps = list_experiences(20)
    assert any(e.get("action") == "browse_test" for e in exps)
    assert "trajectory_frames" in exps[0] or any("trajectory_frames" in e for e in exps)
    mem_table = experiences_table_rows(20)
    assert mem_table and "复用次数" in mem_table[0]

    # 旧路径仍可读
    assert Path(settings.EXPERIMENTS_DIR).is_dir()
    assert Path(settings.EXPERIENCE_DIR).is_dir()
    # 任意旧 json 不应因新字段而读崩
    for p in list(Path(settings.EXPERIMENTS_DIR).glob("*.json"))[:5]:
        json.loads(p.read_text(encoding="utf-8"))

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "experiments_table_rows" in app
    assert "experiences_table_rows" in app
    assert "dataframe" in app

    print("SMOKE_PHASE7_STEP3_OK", saved["experiment_id"])


if __name__ == "__main__":
    main()
