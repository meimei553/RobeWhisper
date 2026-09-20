# -*- coding: utf-8 -*-
"""第 10 期 · 步骤 2：实验落盘接入 run_snapshot 验收。"""

from __future__ import annotations

import json
import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    os.environ["SAFETY_MODE"] = "clip"
    os.environ["ENGINE_TIMEOUT_SEC"] = "30"

    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from core.bootstrap import create_pipeline
    from core.browse_tables import experiments_table_rows
    from core.experiment_store import build_experiment_record, list_recent_experiments
    from core.run_snapshot import snapshot_contains_secrets
    from core.schemas import TaskSpec

    # 旧调用方式（不传快照）仍自动带上
    legacy = build_experiment_record(
        raw_text="旧式调用",
        task_spec={"action": "home", "target": ""},
        sim_result={"ok": True, "trajectory": [], "metrics": {}},
        ok=True,
        adapters={"llm": "mock_llm", "engine": "mujoco_engine", "robot": "mock_robot"},
        model_ref="default",
    )
    assert "run_snapshot" in legacy
    assert snapshot_contains_secrets(legacy["run_snapshot"]) == []

    pipe = create_pipeline()
    result = pipe.run_instruction("回零", model_ref="default", real_sim_real=False, save_data=True)
    assert result.ok, result.to_dict()
    exp_meta = (result.data or {}).get("experiment") or {}
    assert exp_meta.get("ok") == "true"
    path = Path(exp_meta["path"])
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "run_snapshot" in data
    snap = data["run_snapshot"]
    assert snap.get("model_ref") == "default"
    assert snap.get("adapters", {}).get("engine", {}).get("name")
    assert snapshot_contains_secrets(snap) == []
    blob = json.dumps(data, ensure_ascii=False)
    assert "sk-" not in blob.lower()

    # 列表兼容旧记录 + 新字段
    rows = list_recent_experiments(5)
    assert rows
    assert "engine" in rows[0] and "model_ref" in rows[0]
    # 无快照的假旧记录不应让列表崩溃
    table = experiments_table_rows(5)
    assert table and "引擎" in table[0] and "模型" in table[0]

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

    print(
        "SMOKE_PHASE10_STEP2_OK",
        "id",
        data.get("experiment_id"),
        "engine",
        snap["adapters"]["engine"]["name"],
    )


if __name__ == "__main__":
    main()
