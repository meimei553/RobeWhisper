# -*- coding: utf-8 -*-
"""
能力可见与开闭提示 · 步骤5 总验

串联步骤1–4烟雾 + 默认安全 + 未堵死第12期 + 复跑 phase11 相关。
用法：python -m core.smoke_feature_visible
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _run_module(mod: str) -> str:
    r = subprocess.run(
        [sys.executable, "-m", mod],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        raise AssertionError(f"{mod} 失败:\n{out}")
    return out


def _assert_example_defaults() -> None:
    """示例与推荐默认：真机/API/RSR 都关。"""
    ex = (_ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"(?m)^USE_REAL_ROBOT\s*=\s*false\s*$", ex), "示例须默认关真机"
    assert re.search(r"(?m)^USE_REAL_SIM_REAL\s*=\s*false\s*$", ex), "示例须默认关 RSR"
    # LLM_BACKEND=mock 至少出现一次（文件里可能写两次）
    assert "LLM_BACKEND=mock" in ex


def _assert_app_surface() -> None:
    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    must = [
        "feature_catalog_markdown",
        "开闭状态",
        "自检 HTTP 桥是否通",
        "自检云端 API 是否通",
        "build_rsr_status_hint",
        "probe_llm_api",
        "不会做校准",
    ]
    for s in must:
        assert s in app, f"网站缺少：{s}"


def _assert_phase12_door_open() -> None:
    """第12期已完成后仍须：真优先口 + 伪保底 + 送单入口都在（不堵死 13–15）。"""
    rsr = (_ROOT / "core" / "rsr_loop.py").read_text(encoding="utf-8")
    assert "extract_real_trajectory" in rsr
    assert "allow_pseudo_real" in rsr or "prefer_real" in rsr
    assert "pseudo_real" in rsr
    assert 'source = "robot"' in rsr or "source = 'robot'" in rsr
    assert "require_real" in rsr or "RSR_REQUIRE" in (
        _ROOT / "config" / "settings.py"
    ).read_text(encoding="utf-8")

    panel = (_ROOT / "frontend" / "capability_panel.py").read_text(encoding="utf-8")
    assert "真轨迹" in panel and "伪对照" in panel

    from plugins.robot.base import BaseRobot

    assert hasattr(BaseRobot, "execute_task")


def _assert_contract_names() -> None:
    from core.schemas import ApiResult, SimResult, TaskSpec

    # 主字段名抽检（未改名）
    ts = TaskSpec(task_id="t1", action="grab", target="cup")
    d = ts.to_dict()
    for k in ("task_id", "action", "target", "constraints", "params", "source", "raw_text"):
        assert k in d
    sr = SimResult(task_id="t1", ok=True, trajectory=[])
    sd = sr.to_dict()
    for k in ("task_id", "ok", "trajectory", "metrics", "message"):
        assert k in sd
    ar = ApiResult.success("x")
    ad = ar.to_dict()
    assert "ok" in ad and "data" in ad and "message" in ad


def main() -> None:
    # 步骤 1–4
    for mod, token in [
        ("core.smoke_feature_visible_step1", "SMOKE_FEATURE_VISIBLE_STEP1_OK"),
        ("core.smoke_feature_visible_step2", "SMOKE_FEATURE_VISIBLE_STEP2_OK"),
        ("core.smoke_feature_visible_step3", "SMOKE_FEATURE_VISIBLE_STEP3_OK"),
        ("core.smoke_feature_visible_step4", "SMOKE_FEATURE_VISIBLE_STEP4_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    _assert_app_surface()
    _assert_example_defaults()
    _assert_phase12_door_open()
    _assert_contract_names()

    # 复跑第11期相关 + RSR 回流仍通
    for mod, token in [
        ("core.smoke_phase11_step4", "SMOKE_PHASE11_STEP4_OK"),
        ("core.smoke_phase6_step3", "SMOKE_PHASE6_STEP3_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    print("SMOKE_FEATURE_VISIBLE_OK")


if __name__ == "__main__":
    main()
