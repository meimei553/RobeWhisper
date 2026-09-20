@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  echo 未找到 python。请先安装 Python 3.10+。
  pause
  exit /b 1
)
echo [RobeWhisper] 启动前后端分离网站 http://127.0.0.1:8080
echo 页面在 web\ ，接口在 backend\ 。旧版 Streamlit 请双击「一键启动旧版Streamlit.bat」。
echo 关闭本窗口即停止。
python -m backend.server
if errorlevel 1 (
  echo 启动失败。若提示缺少 fastapi，请先运行：python -m pip install fastapi uvicorn python-multipart
  pause
  exit /b 1
)
pause