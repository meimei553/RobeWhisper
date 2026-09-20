# RobeWhisper · 机器人自然语言编程平台

零基础可先在本机调试；**长期公网访问请用方案 D（云端）**。  
默认不连真机、不调用大模型 API，用 Mock 也能完整演示。

## 你需要准备什么

1. 已安装 **Python 3.10+**（命令行能运行 `python --version`）
2. 本项目文件夹：`RobeWhisper`

## 本机临时启动（调试）

```text
python -m pip install -r requirements.txt
```

或双击：`安装依赖.bat`  
再双击：`一键启动网站.bat`  
打开：[http://127.0.0.1:8501](http://127.0.0.1:8501)

关掉黑窗口即停止（这不是长期公网站）。

## 方案 D · 云端长期存在（推荐）

完整步骤见：`core/云端部署_方案D.txt`

两条常用路：

1. **Streamlit Community Cloud（免费）**  
   项目推到 GitHub → [share.streamlit.io](https://share.streamlit.io) 部署 → 得到 `https://xxxx.streamlit.app`

2. **云服务器 + Docker**  
   ```text
   docker compose up -d --build
   ```  
   访问 `http://服务器公网IP:8501`

已提供：`Dockerfile`、`docker-compose.yml`、`packages.txt`、`.streamlit/config.toml`

## 默认配置（不用改也能跑）

| 项 | 默认 | 说明 |
|---|---|---|
| `ENGINE_BACKEND` | `mujoco` | 虚拟机械臂仿真 |
| `LLM_BACKEND` | `mock` | 不调网上大模型 |
| `ROBOT_BACKEND` | `mock` | 不发真机 |
| `USE_REAL_ROBOT` | `false` | 真机发送关闭 |
| `USE_REAL_SIM_REAL` | `false` | RSR 校准关闭 |
| `RSR_REQUIRE_REAL_TRAJECTORY` | `false` | 严模式关（无真轨迹仍可伪对照） |

## 想用大模型 API 时

本地：复制 `.env.example` 为 `.env` 后填写。  
云端：在平台 Secrets 里配置（不要把密钥提交到 Git）。

## 真机联调

见 `plugins/robot/真机联调检查清单.txt`（云端一般连不到家里真机，真机请本机联调）。

演示：`core/演示剧本.txt`  
回归：`core/回归与启动一页纸.txt`

## 快速自检

```text
python -m core.smoke_step3
python -m core.smoke_phase7
python -m core.smoke_phase12
python -m core.smoke_phase13
python -m core.smoke_phase14
python -m core.smoke_feature_visible
```

第 1–14 期已收口时可看：`core/回归与启动一页纸.txt`

## 常见问题

- **本机打不开**：确认 `一键启动网站.bat` 窗口还在，地址是 `127.0.0.1:8501`
- **云端 MuJoCo 报错**：确认仓库含 `packages.txt`，并重新 Deploy
- **改了配置没变化**：本机重启 bat；云端在控制台 Reboot / Redeploy
