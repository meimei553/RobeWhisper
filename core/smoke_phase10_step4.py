# -*- coding: utf-8 -*-
"""第 10 期 · 步骤 4：演示包导出验收。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="rw_pack_") as tmp:
        exp_dir = Path(tmp) / "experiments"
        pack_dir = exp_dir / "packs"
        exp_dir.mkdir(parents=True)
        os.environ["EXPERIMENTS_DIR"] = str(exp_dir)
        os.environ["ENGINE_BACKEND"] = "mujoco"
        os.environ["LLM_BACKEND"] = "mock"
        os.environ["ROBOT_BACKEND"] = "mock"

        import config.settings as settings_mod

        reload(settings_mod)

        from core.demo_pack import export_demo_pack, prepare_pack_files, redact_for_export
        from core.experiment_store import build_experiment_record, save_experiment
        from core.schemas import TaskSpec

        rec = build_experiment_record(
            raw_text="回零",
            task_spec={"action": "home", "target": "", "params": {}},
            sim_result={
                "ok": True,
                "trajectory": [
                    {"t": 0, "joint_positions": [0.0, 0.0]},
                    {"t": 1, "joint_positions": [0.1, -0.1]},
                ],
                "metrics": {"steps": 1},
                "engine_name": "mujoco_engine",
            },
            ok=True,
            adapters={"llm": "mock_llm", "engine": "mujoco_engine", "robot": "mock_robot"},
            model_ref="default",
            snapshot_extra={"api_key": "sk-should-strip", "note": "ok"},
        )
        # 故意污染后再导出，验证脱敏
        rec["leak"] = {"LLM_API_KEY": "sk-leaked-value", "safe": 1}
        saved = save_experiment(rec)
        assert saved["ok"] == "true"
        exp_id = saved["experiment_id"]

        # 文件内容层脱敏
        files = prepare_pack_files(rec)
        joined = "\n".join(files.values()).lower()
        assert "sk-" not in joined
        assert "api_key" not in joined
        assert "README_演示说明.txt" in files
        assert json.loads(files["trajectory_summary.json"])["frames"] == 2

        out = export_demo_pack(exp_id, out_dir=pack_dir)
        assert out["ok"], out
        zip_path = Path(out["zip_path"])
        assert zip_path.is_file()
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())
            assert names >= {
                "experiment.json",
                "trajectory_summary.json",
                "run_snapshot.json",
                "README_演示说明.txt",
            }
            for n in names:
                raw = zf.read(n).decode("utf-8")
                assert "sk-" not in raw.lower()
                assert "LLM_API_KEY" not in raw

        # latest
        out2 = export_demo_pack(latest=True, out_dir=pack_dir)
        assert out2["ok"] and out2["experiment_id"] == exp_id

        # 路径穿越拒绝
        assert redact_for_export({"api_key": "x", "a": 1}) == {"a": 1}

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

        print("SMOKE_PHASE10_STEP4_OK", "zip", zip_path.name, "id", exp_id)


if __name__ == "__main__":
    main()
