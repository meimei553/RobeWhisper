# -*- coding: utf-8 -*-
"""第 14 期 · 步骤 3：Pipeline / 引擎顺序执行。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.bootstrap import create_llm, create_robot
    from core.multi_step_exec import iter_step_specs, merge_step_sim_results
    from core.pipeline import Pipeline
    from core.schemas import SimResult, TaskSpec
    from plugins.engines.mock_engine import MockEngine
    from plugins.llm.mock_llm import MockLLM

    # 展开
    parent = TaskSpec(
        task_id="p1",
        action="home",
        target="",
        steps=[
            {"action": "home", "target": "", "constraints": {}, "params": {}},
            {"action": "grab", "target": "red_cup", "constraints": {}, "params": {"steps": 2}},
        ],
    )
    leaves = iter_step_specs(parent)
    assert len(leaves) == 2
    assert leaves[0].action == "home" and leaves[0].steps == []
    assert leaves[1].action == "grab"

    # Mock 多步成功
    eng = MockEngine()
    llm = MockLLM()
    pipe = Pipeline(llm=llm, engine=eng, robot=create_robot())
    r = pipe.run_instruction("先回零再抓红色杯子", model_ref="default", real_sim_real=False, save_data=False)
    assert r.ok, r.to_dict()
    sim = r.data["sim_result"]
    assert sim["ok"] is True
    assert (sim.get("metrics") or {}).get("multi_step") is True
    assert (sim.get("metrics") or {}).get("step_count") == 2
    assert (sim.get("metrics") or {}).get("step_actions") == ["home", "grab"]
    assert "2" in (r.message or "") or "步" in (r.message or "")
    assert r.data.get("multi_step", {}).get("step_count") == 2

    # wait 单步
    r_w = pipe.run_instruction("等待一下", model_ref="default", real_sim_real=False, save_data=False)
    assert r_w.ok, r_w.to_dict()
    assert r_w.data["task_spec"]["action"] == "wait"

    # 旧单步仍通
    r0 = pipe.run_instruction("把红色杯子拿起来", model_ref="default", real_sim_real=False, save_data=False)
    assert r0.ok
    assert (r0.data["sim_result"].get("metrics") or {}).get("multi_step") is not True

    # 第 2 步故意失败可定位
    class _FailSecond(MockEngine):
        def run_task(self, task: TaskSpec) -> SimResult:
            if str(task.task_id).endswith("_s2"):
                return SimResult(task_id=task.task_id, ok=False, message="故意失败", metrics={})
            return super().run_task(task)

    pipe2 = Pipeline(llm=create_llm(), engine=_FailSecond(), robot=create_robot())
    # 直接塞多步：用 llm 解析后再不好注入；改用手动构造走引擎链——通过 parse 后替换较难
    # 用「先回零再抓」走完整 pipeline
    bad = pipe2.run_instruction("先回零再抓红色杯子", model_ref="default", real_sim_real=False, save_data=False)
    assert not bad.ok
    assert "第 2" in (bad.message or "") or "2/" in (bad.message or "")
    assert (bad.data or {}).get("multi_step", {}).get("failed_at") == 2

    # 合并函数
    s1 = SimResult(task_id="a", ok=True, trajectory=[{"t": 0}], metrics={"step_action": "home"})
    s2 = SimResult(task_id="b", ok=True, trajectory=[{"t": 1}], metrics={"step_action": "grab"})
    merged = merge_step_sim_results(parent_task_id="p", step_results=[s1, s2])
    assert merged.ok and merged.metrics.get("step_count") == 2

    # MuJoCo 也能跑多步（若可用）
    try:
        from plugins.engines.mujoco_engine import MujocoEngine

        mj = MujocoEngine()
        pipe_mj = Pipeline(llm=llm, engine=mj, robot=create_robot())
        rm = pipe_mj.run_instruction(
            "先回零再抓红色杯子", model_ref="default", real_sim_real=False, save_data=False
        )
        assert rm.ok, rm.to_dict()
        assert (rm.data["sim_result"].get("metrics") or {}).get("step_count") == 2
    except Exception as exc:
        raise AssertionError(f"MuJoCo 多步失败: {exc}") from exc

    print("SMOKE_PHASE14_STEP3_OK")


if __name__ == "__main__":
    main()
