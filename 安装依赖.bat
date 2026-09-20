@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [RobeWhisper] 正在安装/更新依赖（requirements.txt）...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo 安装失败：请确认已安装 Python 3.10+，且命令 python 可用。
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo 已自动复制 .env.example 为 .env（可按需编辑）。
  )
)

echo 依赖安装完成。
pause
