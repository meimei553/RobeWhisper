# -*- coding: utf-8 -*-
"""第 10 期 · 步骤 3：经验 model_ref 分区与防跨臂验收。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="rw_exp_") as tmp:
        os.environ["EXPERIENCE_DIR"] = tmp
        os.environ["EXPERIENCE_ALLOW_CROSS_MODEL"] = "false"
        os.environ["ENGINE_BACKEND"] = "mujoco"
        os.environ["LLM_BACKEND"] = "mock"
        os.environ["ROBOT_BACKEND"] = "mock"

        import config.settings as settings_mod

        reload(settings_mod)
        import core.experience_store as exp_mod

        reload(exp_mod)

        from core.experience_store import (
            find_experience,
            make_key,
            remember_experience,
        )
        from core.schemas import TaskSpec

        # 臂 A 写入
        remember_experience(
            action="grab",
            target="red_block",
            raw_text="抓红积木 A",
            trajectory=[{"joint_positions": [0.5, -0.3]}],
            ok=True,
            model_ref="arm_a",
        )
        assert (Path(tmp) / f"{make_key('grab', 'red_block', 'arm_a')}.json").exists()

        # 同臂命中
        hit_a = find_experience("grab", "red_block", model_ref="arm_a")
        assert hit_a and hit_a.get("suggested_joint_targets") == [0.5, -0.3]
        assert hit_a.get("_experience_source") == "tagged"

        # 跨臂默认不命中
        miss_b = find_experience("grab", "red_block", model_ref="arm_b")
        assert miss_b is None

        # 旧无标签文件：仅默认族可兼容
        legacy_path = Path(tmp) / f"{make_key('grab', 'red_cup', with_model=False)}.json"
        legacy_path.write_text(
            json.dumps(
                {
                    "key": "grab__red_cup",
                    "action": "grab",
                    "target": "red_cup",
                    "ok": True,
                    "suggested_joint_targets": [0.1, 0.2],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        leg = find_experience("grab", "red_cup", model_ref="default")
        assert leg is not None and leg.get("_legacy_untagged") is True
        assert find_experience("grab", "red_cup", model_ref="arm_b") is None

        # 开跨臂后可命中
        os.environ["EXPERIENCE_ALLOW_CROSS_MODEL"] = "true"
        reload(settings_mod)
        reload(exp_mod)
        from core.experience_store import find_experience as find2

        cross = find2("grab", "red_block", model_ref="arm_b")
        assert cross is not None and cross.get("_experience_source") in {"cross", "tagged", "legacy"}

        os.environ["EXPERIENCE_ALLOW_CROSS_MODEL"] = "false"
        reload(settings_mod)
        reload(exp_mod)

        # Pipeline 传入 model_ref
        import core.bootstrap as bootstrap
        import core.pipeline as pipeline_mod

        reload(bootstrap)
        reload(pipeline_mod)
        from core.bootstrap import create_llm, create_robot
        from plugins.engines.mock_engine import MockEngine

        eng = MockEngine()
        pipe = pipeline_mod.Pipeline(llm=create_llm(), engine=eng, robot=create_robot())
        r = pipe.run_instruction("抓起红色积木", model_ref="arm_demo", real_sim_real=False, save_data=True)
        assert r.ok, r.to_dict()
        tagged = list(Path(tmp).glob("grab__red_block__arm_demo.json"))
        assert tagged, list(Path(tmp).glob("*.json"))

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
            "SMOKE_PHASE10_STEP3_OK",
            "same_arm",
            bool(hit_a),
            "cross_blocked",
            miss_b is None,
            "legacy_default",
            bool(leg),
        )


if __name__ == "__main__":
    main()
