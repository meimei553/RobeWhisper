---
name: robewhisper
description: RobeWhisper 机器人自然语言编程平台的安装、启动、自检与排错操作指南。Use when the user asks to 打开网站、启动项目、安装依赖、运行自检/烟雾测试、修复启动报错，or when setting up, running, or debugging the RobeWhisper project.
---

# RobeWhisper 项目操作指南

## 项目速览

- 机器人自然语言编程平台：中文描述任务 → 自动编排动作 → 虚拟机械臂执行
- 当前架构（2026-09-19 起）：**前后端分离**
  - 后端：FastAPI，入口 `backend/server.py`，端口 **8080**
  - 前端：`web/` 目录静态页面
  - 旧版 Streamlit（端口 8501）保留可用，入口 `frontend/app.py`
- 默认全 Mock：不连真机、不调大模型 API，断网也能完整演示

## 环境要求

- Python 3.10+（命令行能运行 `python --version`）
- Windows 可双击 .bat；其他系统用等价 python 命令

## 首次安装

1. `python -m pip install -r requirements.txt`
2. 若无 `.env`：复制 `.env.example` 为 `.env`（默认值即可运行）
3. 若启动报缺 fastapi：`python -m pip install fastapi uvicorn python-multipart`

## 启动网站

首选（新版）：

```bash
python -m backend.server
# 打开 http://127.0.0.1:8080
```

旧版 Streamlit：`streamlit run frontend/app.py` → http://127.0.0.1:8501

停止：关闭运行窗口或 Ctrl+C。页面分类：自然语言 / 模型与物理 / 实验与经验 / 能力与诊断。

## 自检（由浅到深，改代码后必跑）

```bash
python -m core.smoke_step3
python -m core.smoke_phase7
python -m core.smoke_phase12
python -m core.smoke_phase13
python -m core.smoke_phase14
python -m core.smoke_feature_visible
```

反馈循环：全部通过才算改动收口；任一失败 → 看报错修复 → 重跑，通过后才交付。

## 常见报错处理

| 现象 | 处理 |
|---|---|
| 找不到 python | 安装 Python 3.10+，安装时勾选 Add to PATH |
| 缺 fastapi / uvicorn | `python -m pip install fastapi uvicorn python-multipart` |
| 端口被占 / 页面打不开 | 关闭所有旧的启动黑窗口后重新启动 |
| 云端 MuJoCo 报错 | 确认仓库含 `packages.txt`，然后在平台 Redeploy |

## 配置说明（.env）

安全默认，勿随意改：`LLM_BACKEND=mock`、`ROBOT_BACKEND=mock`、`USE_REAL_ROBOT=false`

- 接真实大模型：填齐 `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL_NAME`，再把 `LLM_BACKEND=api`；缺任一项自动回退 mock，网站不崩
- 真机联调：见 `plugins/robot/真机联调检查清单.txt`；真机只能本机联调，云端连不到
- 无真机验真轨迹：`python -m plugins.robot.local_fake_receiver --with-trajectory`

## 项目进度备忘（避免重复劳动）

- 第 1–14 期已完成；补强包一已收口（总验：`python -m core.smoke_boost1`）
- 下一步：补强包二；第 15 期（可视化+部署+Kimi）最后做，两包完成前不要开

## 安全红线

- 绝不提交 `.env`（已在 .gitignore 中）
- 真机发送默认关闭；用户明确要求前，不得把 `USE_REAL_ROBOT` 改为 true
