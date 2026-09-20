# -*- coding: utf-8 -*-
"""阶段 1 · 步骤 1：引擎安装与最小加载探测（不进入业务适配器）。"""

from __future__ import annotations

def probe_mujoco() -> tuple[bool, str]:
    try:
        import mujoco
    except Exception as exc:  # noqa: BLE001
        return False, f"import 失败: {exc}"

    xml = """
    <mujoco model="probe_arm">
      <worldbody>
        <body name="link1" pos="0 0 0.1">
          <joint name="j0" type="hinge" axis="0 0 1"/>
          <geom type="capsule" fromto="0 0 0 0 0 0.2" size="0.03"/>
        </body>
      </worldbody>
    </mujoco>
    """
    try:
        model = mujoco.MjModel.from_xml_string(xml)
        data = mujoco.MjData(model)
        data.ctrl[:] = 0.0 if model.nu else None
        # 直接改 qpos 再步进，验证动力学可跑
        if model.nq > 0:
            data.qpos[0] = 0.2
        mujoco.mj_step(model, data)
        q0 = float(data.qpos[0]) if model.nq > 0 else 0.0
        return True, f"MUJOCO_OK version={mujoco.__version__} nq={model.nq} q0={q0}"
    except Exception as exc:  # noqa: BLE001
        return False, f"加载/步进失败: {exc}"


def probe_pybullet() -> tuple[bool, str]:
    try:
        import pybullet as p
    except Exception as exc:  # noqa: BLE001
        return False, f"import 失败: {exc}"
    try:
        cid = p.connect(p.DIRECT)
        p.resetSimulation()
        p.disconnect(cid)
        return True, f"PYBULLET_OK version={getattr(p, 'getAPIVersion', lambda: 'unknown')()}"
    except Exception as exc:  # noqa: BLE001
        return False, f"连接失败: {exc}"


def main() -> None:
    mj_ok, mj_msg = probe_mujoco()
    print(mj_msg)
    if mj_ok:
        print("ENGINE_CHOICE=mujoco")
        print("PROBE_STEP1_OK")
        return

    print("mujoco 不可用，尝试备选 pybullet …")
    pb_ok, pb_msg = probe_pybullet()
    print(pb_msg)
    if pb_ok:
        print("ENGINE_CHOICE=pybullet")
        print("PROBE_STEP1_OK")
        return

    print("ENGINE_CHOICE=none")
    raise SystemExit("PROBE_STEP1_FAIL")


if __name__ == "__main__":
    main()
