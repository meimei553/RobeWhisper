# -*- coding: utf-8 -*-
"""阶段 7 · 步骤 1：启动与依赖说明验收。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install -r requirements.txt" in readme
    assert "127.0.0.1:8501" in readme
    assert "LLM_BACKEND" in readme and "mock" in readme
    assert "USE_REAL_ROBOT" in readme
    assert (_ROOT / "一键启动网站.bat").exists()
    assert (_ROOT / "安装依赖.bat").exists()
    # 方案 D 云端文件改为可选（用户已选本机优先，不堵后续再部署）
    assert not (_ROOT / "install_autostart.bat").exists()
    assert not (_ROOT / "start_website_hidden.vbs").exists()

    bat_start = (_ROOT / "一键启动网站.bat").read_text(encoding="utf-8")
    bat_install = (_ROOT / "安装依赖.bat").read_text(encoding="utf-8")
    assert "streamlit run frontend/app.py" in bat_start
    assert "127.0.0.1" in bat_start and "8501" in bat_start
    assert "requirements.txt" in bat_install
    assert ".env.example" in bat_start or ".env.example" in bat_install

    # 无 API 密钥时 mock 全链路仍通
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    ok = bootstrap.create_pipeline().run_instruction("回零")
    assert ok.ok, ok.to_dict()

    print("SMOKE_PHASE7_STEP1_OK")


if __name__ == "__main__":
    main()
