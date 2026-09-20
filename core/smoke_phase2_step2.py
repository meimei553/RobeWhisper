# -*- coding: utf-8 -*-
"""阶段 2 · 步骤 2：模型目录与切换加载验收。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    import os
    from importlib import reload

    os.environ["ENGINE_BACKEND"] = "mujoco"
    import config.settings as settings_mod

    reload(settings_mod)
    import core.bootstrap as bootstrap

    reload(bootstrap)

    from core.model_catalog import list_model_options, save_uploaded_model, uploads_dir
    from core.schemas import TaskSpec
    from plugins.engines.mujoco_engine import MujocoEngine

    opts = list_model_options()
    assert any(o["ref"] == "default" for o in opts)
    assert any("mujoco_testdata" in o["ref"] for o in opts)

    tiny = b"""
    <mujoco model="upload_probe">
      <worldbody>
        <body name="b">
          <joint name="j0" type="hinge" axis="0 0 1"/>
          <geom type="sphere" size="0.05"/>
        </body>
      </worldbody>
    </mujoco>
    """
    saved = save_uploaded_model("probe_upload.xml", tiny)
    assert saved["ok"] == "true", saved
    assert (uploads_dir() / "probe_upload.xml").exists()

    eng = bootstrap.create_engine()
    assert isinstance(eng, MujocoEngine)
    eng.load(saved["ref"])
    eng.reset()
    s1 = eng.get_state()
    assert len(s1.get("joint_positions") or []) >= 1

    eng.load("mujoco_testdata/model.xml")
    eng.reset()
    s2 = eng.get_state()
    assert len(s2.get("joint_positions") or []) >= 1

    eng.load("default")
    eng.reset()
    s3 = eng.get_state()
    assert len(s3.get("joint_positions") or []) == 2

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
    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "import mujoco" not in app
    assert "list_model_options" in app and "save_uploaded_model" in app

    print("SMOKE_PHASE2_STEP2_OK")
    print("options", len(opts), "upload_ref", saved["ref"])
    print("nq_default", len(s3.get("joint_positions") or []))


if __name__ == "__main__":
    main()
