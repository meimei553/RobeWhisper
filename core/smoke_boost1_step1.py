# -*- coding: utf-8 -*-
"""补强包一 · 步骤 1：位姿旁路契约 + 代理摘要键名。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.pose_grounding_contract import (
        METRIC_OBJECT_XPOS,
        POSE_SOURCE_NONE,
        POSE_SOURCE_SCENE,
        PROXY_SUMMARY_KEYS,
        build_proxy_summary,
        empty_pose_metrics,
        has_forged_object_pose,
        pose_source_label,
        sanitize_pose_metrics,
        validate_pose_source,
    )
    from core.schemas import TaskSpec

    assert validate_pose_source("scene_model")
    assert validate_pose_source("none")
    assert not validate_pose_source("camera")
    assert not validate_pose_source("vision")

    none_m = empty_pose_metrics(has_scene=False)
    assert none_m["pose_source"] == POSE_SOURCE_NONE
    assert none_m[METRIC_OBJECT_XPOS] is None
    assert none_m["ee_goal_xy"] is None
    assert not has_forged_object_pose(none_m, has_scene=False)

    scene_m = empty_pose_metrics(has_scene=True)
    assert scene_m["pose_source"] == "uncertain"
    assert scene_m[METRIC_OBJECT_XPOS] is None  # 步骤1不填假成功坐标

    # 无场景若有人塞了坐标 → 判伪造，sanitize 清掉
    forged = {
        "pose_source": POSE_SOURCE_SCENE,
        "object_xpos": [0.3, 0.1, 0.04],
        "ee_goal_xy": [0.3, 0.1],
    }
    assert has_forged_object_pose(forged, has_scene=False)
    clean = sanitize_pose_metrics(forged, has_scene=False)
    assert clean["pose_source"] == POSE_SOURCE_NONE
    assert clean["object_xpos"] is None
    assert clean["ee_goal_xy"] is None
    assert not has_forged_object_pose(clean, has_scene=False)

    # 有场景允许保留坐标
    ok_scene = sanitize_pose_metrics(
        {"pose_source": POSE_SOURCE_SCENE, "object_xpos": [0.36, 0.18, 0.04], "ee_goal_xy": [0.36, 0.18]},
        has_scene=True,
    )
    assert ok_scene["pose_source"] == POSE_SOURCE_SCENE
    assert ok_scene["object_xpos"] is not None

    lab = pose_source_label(POSE_SOURCE_SCENE)
    assert "相机" in lab or "仿真" in lab
    assert "看见" not in lab

    summary = build_proxy_summary(
        metrics={"pose_source": "none", "grasp_proxy": "no_scene", "contact_scene": False},
        multi_step={"step_count": 2},
        rsr={"reference_source": "pseudo_real"},
    )
    for k in PROXY_SUMMARY_KEYS:
        assert k in summary
    assert summary["multi_step"] is True
    assert summary["grasp_proxy"] == "no_scene"

    # TaskSpec 主字段仍在；steps 可选空
    d = TaskSpec(task_id="t", action="grab", target="cup").to_dict()
    for k in ("task_id", "action", "target", "constraints", "params", "source", "raw_text", "steps"):
        assert k in d
    assert d["steps"] == []

    doc = _ROOT / "core" / "场景位姿契约_补强包一.txt"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "scene_model" in text
    assert "不是相机" in text or "非相机" in text
    assert "PROXY_SUMMARY" in text or "pose_source" in text

    print("SMOKE_BOOST1_STEP1_OK")


if __name__ == "__main__":
    main()
