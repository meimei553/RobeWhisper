# -*- coding: utf-8 -*-
"""阶段4·步骤4：网站集成验收。"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "list_recent_experiments" in app
    assert "list_experiences" in app
    assert "experience_hit" in app
    assert "st.chat_input" in app
    assert "import mujoco" not in app

    try:
        with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as resp:
            assert resp.status == 200
        site = "UP"
    except Exception:
        site = "DOWN"

    print("SMOKE_PHASE4_STEP4_OK", "site", site)


if __name__ == "__main__":
    main()
