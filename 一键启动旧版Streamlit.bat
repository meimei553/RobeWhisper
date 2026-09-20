@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo 未找到 python 命令。请先安装 Python 3.10+，并勾选「Add to PATH」。
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo 已自动复制 .env.example 为 .env
  )
)

REM 若旧网站进程仍占用 8501，先尽量结束，避免打开到半旧代码
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
  echo 发现旧网站进程 %%p ，正在关闭...
  taskkill /F /PID %%p >nul 2>&1
)

echo [RobeWhisper] 启动临时网站 http://127.0.0.1:8501
echo 关闭本窗口或按 Ctrl+C 可停止。
echo 详细说明见：下次打开网站.txt
echo.

REM 跳过 Streamlit 首次邮箱提问；不采集使用统计
if not exist ".streamlit" mkdir ".streamlit"
if not exist ".streamlit\credentials.toml" (
  >".streamlit\credentials.toml" echo [general]
  >>".streamlit\credentials.toml" echo email = ""
)
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

python -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
if errorlevel 1 (
  echo.
  echo 启动失败。若提示缺少 streamlit/mujoco，请先双击「安装依赖.bat」。
  pause
  exit /b 1
)

pause
