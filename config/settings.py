# -*- coding: utf-8 -*-
"""
RobeWhisper 配置（从环境变量 / 本地 .env 读取）

说明：
- 业务代码应从此处读配置，不要在页面/插件里写死本机路径或密钥。
- 真实密钥只放在本地 .env（已 gitignore），不要写进本文件。
- 缺 API 配置时 create_llm 会回退 mock，保证网站不崩。
"""

from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（本文件位于 config/ 下）
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path | None = None) -> None:
    """
    轻量加载 .env（不依赖 python-dotenv）。
    规则：不覆盖进程里已有的环境变量（烟雾测试 / 系统环境优先）。
    """
    env_path = path or (PROJECT_ROOT / ".env")
    if not env_path.is_file():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except Exception:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = val[1:-1]
        # 已存在则保留（含烟雾里预先写入的值）
        if key not in os.environ:
            os.environ[key] = val


# 每次 import / reload 时先灌入 .env
_load_dotenv()

# ---------- 运行与部署 ----------
# mujoco/local：真仿真；mock：假引擎回退；remote：日后恒定/远程引擎
ENGINE_BACKEND: str = os.getenv("ENGINE_BACKEND", "mujoco")
ROBOT_BACKEND: str = os.getenv("ROBOT_BACKEND", "mock")
LLM_BACKEND: str = os.getenv("LLM_BACKEND", "mock")

APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT: int = int(os.getenv("APP_PORT", "8501"))

# ---------- 数据目录（相对项目根；可被环境变量覆盖） ----------
MODELS_DIR: Path = PROJECT_ROOT / os.getenv("MODELS_DIR", "models")
EXPERIMENTS_DIR: Path = PROJECT_ROOT / os.getenv("EXPERIMENTS_DIR", "experiments")
EXPERIENCE_DIR: Path = PROJECT_ROOT / os.getenv("EXPERIENCE_DIR", "experience")

# 默认内置模型（相对 MODELS_DIR；勿写死盘符绝对路径）
DEFAULT_MODEL_REL: str = os.getenv("DEFAULT_MODEL_REL", "builtin_arm2/model.xml")
default_model_rel = DEFAULT_MODEL_REL


def default_model_path() -> Path:
    """返回默认模型的绝对 Path，始终基于 MODELS_DIR 拼接。"""
    return (MODELS_DIR / DEFAULT_MODEL_REL).resolve()


# ---------- 超时（秒） ----------
ENGINE_TIMEOUT_SEC: int = int(os.getenv("ENGINE_TIMEOUT_SEC", "30"))
LLM_TIMEOUT_SEC: int = int(os.getenv("LLM_TIMEOUT_SEC", "60"))
ROBOT_TIMEOUT_SEC: int = int(os.getenv("ROBOT_TIMEOUT_SEC", "30"))

# ---------- 大模型 API（阶段 3；未配置时保持空字符串） ----------
LLM_API_BASE: str = os.getenv("LLM_API_BASE", "")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "")


def llm_api_configured() -> bool:
    """是否具备调用云端 LLM 的最小配置。"""
    return bool(str(LLM_API_BASE).strip() and str(LLM_API_KEY).strip() and str(LLM_MODEL_NAME).strip())


def effective_llm_backend() -> str:
    """
    实际会用的解析后端。
    配置写 api 但三项不齐 → mock（与 bootstrap.create_llm 一致）。
    """
    want = str(LLM_BACKEND or "mock").strip().lower()
    if want in {"api", "cloud", "openai"} and llm_api_configured():
        return "api"
    return "mock"


def llm_config_note() -> str:
    """给诊断面板的短说明（空字符串=无需额外警告）。"""
    want = str(LLM_BACKEND or "mock").strip().lower()
    if want in {"api", "cloud", "openai"} and not llm_api_configured():
        return (
            "已设 LLM_BACKEND=api，但 API 地址/密钥/模型名未配齐，"
            "已自动回退 mock，网站可继续用。请编辑项目根目录 .env 后重启网站。"
        )
    if effective_llm_backend() == "api":
        return "语言解析已使用云端 api；网络失败时单次指令会友好失败，不会把网站打崩。"
    return ""


# ---------- 真机 / ROS（阶段 5） ----------
ROS_DOMAIN_ID: str = os.getenv("ROS_DOMAIN_ID", "")
ROS_EXECUTE_TOPIC: str = os.getenv("ROS_EXECUTE_TOPIC", "/robewhisper/execute_task")
ROBOT_EXECUTE_ENDPOINT: str = os.getenv("ROBOT_EXECUTE_ENDPOINT", "")
USE_REAL_ROBOT: bool = os.getenv("USE_REAL_ROBOT", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def robot_http_configured() -> bool:
    """HTTP 真机桥是否具备最小配置。"""
    return bool(ROBOT_EXECUTE_ENDPOINT.strip())


def robot_ros_configured() -> bool:
    """
    ROS 桥是否具备最小配置。

    需显式设置 ROS_DOMAIN_ID（避免仅有默认 topic 就被当成已配置）。
    rclpy 是否安装在运行时再判定。
    """
    return bool(ROS_DOMAIN_ID.strip())


# ---------- Real-Sim-Real（阶段 6）----------
USE_REAL_SIM_REAL: bool = os.getenv("USE_REAL_SIM_REAL", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
RSR_CALIB_GAIN: float = float(os.getenv("RSR_CALIB_GAIN", "0.5"))
# 第12期：true=无合格真轨迹则跳过 RSR（严模式）；默认 false=允许伪对照保底
RSR_REQUIRE_REAL_TRAJECTORY: bool = os.getenv(
    "RSR_REQUIRE_REAL_TRAJECTORY", "false"
).strip().lower() in {"1", "true", "yes", "on"}

# ---------- 安全闸（第 9 期）----------
SAFETY_MODE: str = os.getenv("SAFETY_MODE", "clip").strip().lower() or "clip"

# ---------- 经验分区（第 10 期）----------
EXPERIENCE_ALLOW_CROSS_MODEL: bool = os.getenv(
    "EXPERIENCE_ALLOW_CROSS_MODEL", "false"
).strip().lower() in {"1", "true", "yes", "on"}
