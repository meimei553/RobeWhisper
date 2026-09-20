# -*- coding: utf-8 -*-
"""第 13 期 · 步骤 1：接触场景与开关契约。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from config import settings
    from core.contact_scene_contract import (
        CONTACT_EE_GEOM,
        CONTACT_OBJECT_BODY,
        CONTACT_SCENE_MODEL_REL,
        GRASP_PROXY_NO_SCENE,
        empty_contact_metrics,
        is_contact_scene_model_ref,
        validate_grasp_proxy,
    )
    from core.model_catalog import list_model_options
    from core.schemas import TaskSpec

    # 文件存在
    contact_path = settings.MODELS_DIR / CONTACT_SCENE_MODEL_REL
    assert contact_path.is_file(), f"缺少接触场景: {contact_path}"
    default_path = settings.default_model_path()
    assert default_path.is_file()
    assert "builtin_arm2" in str(default_path).replace("\\", "/")
    assert "contact" not in Path(settings.DEFAULT_MODEL_REL).as_posix() or (
        settings.DEFAULT_MODEL_REL.replace("\\", "/") == "builtin_arm2/model.xml"
    )
    assert settings.DEFAULT_MODEL_REL.replace("\\", "/") == "builtin_arm2/model.xml"

    # 契约：model_ref 识别
    assert is_contact_scene_model_ref("builtin_arm2_contact")
    assert is_contact_scene_model_ref("builtin_arm2_contact/model.xml")
    assert is_contact_scene_model_ref("contact")
    assert not is_contact_scene_model_ref("default")
    assert not is_contact_scene_model_ref("builtin_arm2")
    assert not is_contact_scene_model_ref("")

    m_scene = empty_contact_metrics(has_scene=True)
    m_none = empty_contact_metrics(has_scene=False)
    assert m_none["grasp_proxy"] == GRASP_PROXY_NO_SCENE
    assert m_scene["contact_scene"] is True
    assert validate_grasp_proxy("ok")
    assert validate_grasp_proxy("no_scene")
    assert not validate_grasp_proxy("caught_for_factory")

    # MJCF 含约定体名
    xml = contact_path.read_text(encoding="utf-8")
    assert CONTACT_OBJECT_BODY in xml
    assert CONTACT_EE_GEOM in xml
    assert "freejoint" in xml

    # 目录可选：接触场景出现在下拉，且标签含「接触」
    opts = list_model_options()
    refs = [o["ref"] for o in opts]
    assert "default" in refs
    assert any("builtin_arm2_contact" in r.replace("\\", "/") for r in refs)
    contact_opt = next(o for o in opts if "builtin_arm2_contact" in o["ref"].replace("\\", "/"))
    assert "接触" in contact_opt["label"]

    # 两套模型都能 load（默认不被迫换）
    from core.bootstrap import create_engine

    eng = create_engine()
    eng.load("default")
    assert "builtin_arm2" in str(getattr(eng, "_model_ref", "")).replace("\\", "/")
    # 接触场景
    eng.load("builtin_arm2_contact")
    assert "builtin_arm2_contact" in str(getattr(eng, "_model_ref", "")).replace("\\", "/")
    # 切回默认仍可
    eng.load("default")

    # 主契约字段名未改
    d = TaskSpec(task_id="t", action="grab", target="block").to_dict()
    for k in ("task_id", "action", "target", "constraints", "params", "source", "raw_text"):
        assert k in d

    print("SMOKE_PHASE13_STEP1_OK")


if __name__ == "__main__":
    main()
