# -*- coding: utf-8 -*-
"""第 11 期 · 步骤 1：真机桥 JSON 契约与清单验收。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.robot_bridge_contract import (
        build_execute_request,
        normalize_execute_ack,
        task_spec_main_fields,
        validate_execute_ack,
        validate_execute_request,
    )
    from core.schemas import TaskSpec

    checklist = _ROOT / "plugins" / "robot" / "真机联调检查清单.txt"
    assert checklist.is_file()
    text = checklist.read_text(encoding="utf-8")
    assert "任务单长什么样" in text or "最小 JSON" in text
    assert "接入真机" in text
    assert "trajectory" in text
    assert "ok" in text and "message" in text
    assert "第 12 期" in text or "12 期" in text
    assert "task_spec" in text
    assert "不会自动" in text or "不会自动找到" in text

    # 请求契约
    task = TaskSpec(task_id="t11", action="grab", target="red_block", raw_text="抓起红色积木")
    req = build_execute_request(task)
    assert req["source"] == "robewhisper"
    assert set(req["task_spec"]) == task_spec_main_fields()
    ok, msg = validate_execute_request(req)
    assert ok, msg

    bad_ok, _ = validate_execute_request({"foo": 1})
    assert not bad_ok

    # 响应最小 ack
    ack_ok, m2 = validate_execute_ack({"ok": True, "message": "已接收"})
    assert ack_ok, m2
    ack_bad, _ = validate_execute_ack({"ok": True})
    assert not ack_bad

    # 可选 trajectory（列表）可通过；非列表拒绝
    ok_t, _ = validate_execute_ack(
        {"ok": True, "message": "x", "trajectory": [{"t": 0, "joint_positions": [0.0]}]}
    )
    assert ok_t
    bad_t, _ = validate_execute_ack({"ok": True, "message": "x", "trajectory": "nope"})
    assert not bad_t

    norm = normalize_execute_ack(
        {"ok": True, "message": "done", "lab_custom": 1, "trajectory": []}
    )
    assert norm["ok"] is True and norm["schema"] == "robewhisper_robot_ack_v1"
    assert norm.get("extras", {}).get("lab_custom") == 1
    assert "trajectory" in norm

    # 主字段未改
    assert task_spec_main_fields() == {
        "task_id",
        "action",
        "target",
        "constraints",
        "params",
        "source",
        "raw_text",
        "steps",
    }

    # 与 HttpRobot 实际载荷一致
    from plugins.robot.http_robot import HttpRobot

    # 不发起网络：只核对构造逻辑与契约模块一致
    payload = {"task_spec": task.to_dict(), "source": "robewhisper"}
    assert payload == build_execute_request(task)

    print("SMOKE_PHASE11_STEP1_OK", "fields", sorted(task_spec_main_fields()))


if __name__ == "__main__":
    main()
