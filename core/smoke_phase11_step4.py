# -*- coding: utf-8 -*-
"""第 11 期 · 步骤 4：真发警示文案 + HTTP 只读自检。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from frontend.capability_panel import build_system_status, real_robot_safety_banner
    from core.robot_bridge_probe import probe_http_bridge
    from plugins.robot.local_fake_receiver import start_server

    # 关真发：明确不会动真机
    safe = real_robot_safety_banner(use_real_robot=False, robot_backend="mock")
    assert safe["level"] == "safe"
    blob = " ".join(safe["lines"])
    assert "不会" in blob and ("真" in blob or "虚拟" in blob)

    # 开真发 + http：危险级警示
    danger = real_robot_safety_banner(
        use_real_robot=True,
        robot_backend="http",
        robot_name="http_robot",
        robot_endpoint="http://10.0.0.8:9000/execute_task",
    )
    assert danger["level"] == "danger"
    assert "可能" in " ".join(danger["lines"]) or "小心" in danger["title"]
    assert "10.0.0.8" in danger["endpoint_display"]

    # 开真发但仍 mock：warn
    warn = real_robot_safety_banner(use_real_robot=True, robot_backend="mock")
    assert warn["level"] == "warn"

    status_off = build_system_status(
        llm_backend="mock",
        engine_backend="mujoco",
        robot_backend="mock",
        use_real_robot=False,
        use_rsr_config=False,
        rsr_ui=False,
        robot_name="mock_robot",
        model_ref="default",
        engine_ok=True,
    )
    assert status_off["use_real_robot"] is False
    assert any("不会动" in x or "关" in x for x in status_off["ok_items"])

    status_on = build_system_status(
        llm_backend="mock",
        engine_backend="mujoco",
        robot_backend="http",
        use_real_robot=True,
        use_rsr_config=False,
        rsr_ui=False,
        robot_name="http_robot",
        model_ref="default",
        engine_ok=True,
        robot_endpoint="http://127.0.0.1:9000/execute_task",
    )
    assert status_on["use_real_robot"] is True
    assert len(status_on["issues"]) >= 1
    assert any("真机发送已打开" in x or "可能" in x for x in status_on["issues"])

    # 未配置 endpoint
    empty = probe_http_bridge("")
    assert not empty["ok"]
    assert empty["code"] == "NOT_CONFIGURED"
    assert empty.get("read_only") is True

    # 假接收端 GET 应通
    server, _, _ = start_server(host="127.0.0.1", port=0, daemon_thread=True)
    port = int(server.server_address[1])
    try:
        ok = probe_http_bridge(f"http://127.0.0.1:{port}/execute_task", timeout_sec=3)
        assert ok["ok"], ok
        assert ok["read_only"] is True
        # 错地址
        bad = probe_http_bridge("http://127.0.0.1:1/execute_task", timeout_sec=1)
        assert not bad["ok"]
        assert bad["code"] in {"NETWORK", "TIMEOUT", "INTERNAL"}
    finally:
        server.shutdown()
        server.server_close()

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "probe_http_bridge" in app
    assert "real_robot_safety_banner" in app or "真机发送" in app
    assert "自检 HTTP 桥是否通" in app

    checklist = (_ROOT / "plugins" / "robot" / "真机联调检查清单.txt").read_text(
        encoding="utf-8"
    )
    assert "自检" in checklist or "只读" in checklist

    print("SMOKE_PHASE11_STEP4_OK")


if __name__ == "__main__":
    main()
