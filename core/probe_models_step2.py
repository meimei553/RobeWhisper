# -*- coding: utf-8 -*-
"""阶段 1 · 步骤 2：验证 models/ 内置模型可经 MODELS_DIR 加载。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import settings


def main() -> None:
    import mujoco

    path = settings.default_model_path()
    assert path.exists(), f"默认模型不存在: {path}"
    # 路径必须落在 MODELS_DIR 下（禁止游离绝对路径策略）
    assert settings.MODELS_DIR.resolve() in path.parents or path.parent == settings.MODELS_DIR.resolve()

    model = mujoco.MjModel.from_xml_path(str(path))
    data = mujoco.MjData(model)
    mujoco.mj_step(model, data)

    secondary = (settings.MODELS_DIR / "mujoco_testdata" / "model.xml").resolve()
    assert secondary.exists(), "附带 testdata 模型缺失"

    print("DEFAULT_MODEL", path)
    print("nq", model.nq, "nu", model.nu, "njnt", model.njnt)
    print("SECONDARY_OK", secondary)
    print("PROBE_STEP2_OK")


if __name__ == "__main__":
    main()
