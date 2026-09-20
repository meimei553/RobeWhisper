# -*- coding: utf-8 -*-
"""第 12 期 · 步骤 1：真轨迹契约与提取加固。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _good_frames(n: int = 2, dim: int = 2) -> list[dict]:
    return [{"t": float(i), "joint_positions": [0.1 * i] * dim} for i in range(n)]


def main() -> None:
    from core.rsr_loop import (
        extract_real_trajectory,
        extract_real_trajectory_report,
        is_qualified_real_trajectory,
        run_rsr_iteration,
    )

    # —— 形状合格 / 不合格 ——
    ok, clean, reason = is_qualified_real_trajectory(_good_frames())
    assert ok and len(clean) == 2 and reason == "合格"

    bad_cases = [
        None,
        [],
        "not-a-list",
        [{"t": 0}],  # 无 joint_positions
        [{"t": 0, "joint_positions": []}],
        [
            {"t": 0, "joint_positions": [0.1, 0.2]},
            {"t": 1, "joint_positions": [0.1]},  # 维数不一致
        ],
        [{"t": 0, "joint_positions": [0.0] * 65}],  # 维数过大
    ]
    for case in bad_cases:
        q, frames, _ = is_qualified_real_trajectory(case)  # type: ignore[arg-type]
        assert q is False
        assert frames == []

    # —— 关键：从 data.ack.trajectory 提取（第11期 HttpRobot 形状）——
    rr_ack = {
        "ok": True,
        "code": "OK",
        "message": "ok",
        "data": {
            "ack": {
                "ok": True,
                "message": "ack",
                "trajectory": _good_frames(3, 2),
            },
            "response": {"ok": True, "message": "raw"},
        },
    }
    got = extract_real_trajectory(rr_ack)
    assert len(got) == 3
    assert got[0]["joint_positions"] == [0.0, 0.0]
    rep = extract_real_trajectory_report(rr_ack)
    assert rep["qualified"] is True and rep["frame_count"] == 3

    # —— 从 data.response.trajectory 提取 ——
    rr_resp = {
        "ok": True,
        "data": {"response": {"ok": True, "trajectory": _good_frames(1, 3)}},
    }
    assert len(extract_real_trajectory(rr_resp)) == 1

    # —— data 顶层 trajectory ——
    rr_top = {"ok": True, "data": {"trajectory": _good_frames(2, 2)}}
    assert len(extract_real_trajectory(rr_top)) == 2

    # —— 有键但不合格 → 视为无合格真轨迹（[]），不崩 ——
    rr_bad = {
        "ok": True,
        "data": {
            "ack": {"trajectory": [{"t": 0, "joint_positions": []}]},
            "response": {"trajectory": "oops"},
        },
    }
    assert extract_real_trajectory(rr_bad) == []
    rep_bad = extract_real_trajectory_report(rr_bad)
    assert rep_bad["qualified"] is False
    assert rep_bad["found_raw"] is True  # ack 里见过非空 list 结构… 空关节帧 normalize 后
    # 空 joint 的 list 仍是非空 list，found_raw True；若只有 "oops" 字符串则 found_raw 可能 False
    # 上面 ack 有 list → found_raw True

    # —— 接入 run_rsr：有合格真轨迹 → reference_source=robot ——
    class _FakeEng:
        def list_physics_params(self) -> dict:
            return {"friction": 0.5, "joint_damping": 0.1}

        def set_physics_params(self, **kwargs) -> None:
            return None

    sim = _good_frames(4, 2)
    # 真轨迹与仿真略有偏差，便于校准有数
    real_like = [
        {"t": f["t"], "joint_positions": [x + 0.05 for x in f["joint_positions"]]}
        for f in sim
    ]
    rsr = run_rsr_iteration(
        _FakeEng(),
        sim,
        {"ok": True, "data": {"ack": {"trajectory": real_like}}},
        allow_pseudo_real=True,
    )
    assert rsr.get("reference_source") == "robot"
    assert rsr.get("skipped") is False

    # 无轨迹 → 仍可伪对照（未接真机保底）
    rsr_p = run_rsr_iteration(_FakeEng(), sim, {"ok": True, "data": {}}, allow_pseudo_real=True)
    assert rsr_p.get("reference_source") == "pseudo_real"

    print("SMOKE_PHASE12_STEP1_OK")


if __name__ == "__main__":
    main()
