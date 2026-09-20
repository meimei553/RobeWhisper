# -*- coding: utf-8 -*-
"""第 11 期 · 步骤 3：实验旁路写回 robot_result 验收。"""

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
    from core.robot_bridge_contract import (
        redact_robot_endpoint,
        sanitize_robot_result_for_store,
        task_spec_main_fields,
    )
    from core.run_snapshot import collect_run_snapshot, snapshot_contains_secrets
    from plugins.robot.local_fake_receiver import start_server

    # 脱敏：含账号的 URL 不进展示串
    red = redact_robot_endpoint("http://user:secret@10.0.0.8:9000/execute_task?token=abc")
    assert red["configured"] is True
    assert red["host"] == "10.0.0.8"
    assert "secret" not in red["display"]
    assert "token" not in red["display"]
    assert "user" not in red["display"]

    dirty = {
        "ok": True,
        "code": "OK",
        "message": "x",
        "data": {
            "endpoint": "http://user:pass@127.0.0.1:9000/execute_task",
            "ack": {"ok": True, "message": "已确认"},
            "api_key": "should_drop",
        },
    }
    clean = sanitize_robot_result_for_store(dirty)
    assert clean is not None
    assert "endpoint" not in (clean.get("data") or {})
    assert "endpoint_redacted" in (clean.get("data") or {})
    assert "api_key" not in (clean.get("data") or {})
    assert "pass" not in json.dumps(clean)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["EXPERIMENTS_DIR"] = tmp
        os.environ["ROBOT_BACKEND"] = "mock"
        os.environ["USE_REAL_ROBOT"] = "false"
        os.environ["LLM_BACKEND"] = "mock"
        os.environ["ENGINE_BACKEND"] = "mujoco"

        import config.settings as settings_mod
        import core.bootstrap as bootstrap

        reload(settings_mod)
        reload(bootstrap)

        pipe = bootstrap.create_pipeline()
        result = pipe.run_instruction("把红色杯子拿起来", save_data=True)
        assert result.ok, result.to_dict()
        exp = (result.data or {}).get("experiment") or {}
        exp_id = exp.get("experiment_id")
        assert exp_id
        path = Path(tmp) / f"{exp_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "robot_result" in data
        assert data["robot_result"].get("ok") is True
        assert set(data["task_spec"].keys()) == task_spec_main_fields()
        snap = data.get("run_snapshot") or {}
        assert "robot_bridge" in snap
        assert snap["robot_bridge"]["use_real_robot"] is False
        assert snapshot_contains_secrets(snap) == []

        # HTTP 假端：真发开 → 落盘含脱敏 endpoint
        server, _, _ = start_server(host="127.0.0.1", port=0, daemon_thread=True)
        port = int(server.server_address[1])
        endpoint = f"http://127.0.0.1:{port}/execute_task"
        try:
            os.environ["ROBOT_BACKEND"] = "http"
            os.environ["USE_REAL_ROBOT"] = "true"
            os.environ["ROBOT_EXECUTE_ENDPOINT"] = endpoint
            reload(settings_mod)
            reload(bootstrap)
            pipe2 = bootstrap.create_pipeline()
            r2 = pipe2.run_instruction("回零", save_data=True)
            assert r2.ok, r2.to_dict()
            exp2 = (r2.data or {}).get("experiment") or {}
            data2 = json.loads(
                (Path(tmp) / f"{exp2['experiment_id']}.json").read_text(encoding="utf-8")
            )
            rr = data2["robot_result"]
            assert rr.get("ok") is True
            rr_data = rr.get("data") or {}
            assert "endpoint" not in rr_data
            assert rr_data.get("endpoint_redacted", {}).get("host") == "127.0.0.1"
            assert data2["run_snapshot"]["robot_bridge"]["use_real_robot"] is True
            assert data2["run_snapshot"]["robot_bridge"]["endpoint"]["host"] == "127.0.0.1"

            # 错地址失败也应落盘 robot_result
            os.environ["ROBOT_EXECUTE_ENDPOINT"] = "http://127.0.0.1:1/execute_task"
            os.environ["ROBOT_TIMEOUT_SEC"] = "1"
            reload(settings_mod)
            reload(bootstrap)
            pipe3 = bootstrap.create_pipeline()
            r3 = pipe3.run_instruction("移动一下", save_data=True)
            assert not r3.ok
            exp3 = (r3.data or {}).get("experiment") or {}
            assert exp3.get("experiment_id")
            data3 = json.loads(
                (Path(tmp) / f"{exp3['experiment_id']}.json").read_text(encoding="utf-8")
            )
            assert data3.get("ok") is False
            assert "robot_result" in data3
            assert data3["robot_result"].get("ok") is False
        finally:
            server.shutdown()
            server.server_close()

    # 恢复默认，防误发
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["ROBOT_EXECUTE_ENDPOINT"] = ""
    os.environ.pop("EXPERIMENTS_DIR", None)
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    snap0 = collect_run_snapshot(model_ref="default")
    assert "robot_bridge" in snap0

    checklist = (_ROOT / "plugins" / "robot" / "真机联调检查清单.txt").read_text(
        encoding="utf-8"
    )
    assert "接入真机" in checklist

    print("SMOKE_PHASE11_STEP3_OK")


if __name__ == "__main__":
    main()
