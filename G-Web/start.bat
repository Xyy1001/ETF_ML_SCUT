@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
REM ==================== ETF-ML 预测系统启动脚本 ====================
REM 这个脚本用于启动 Flask 后端服务和可视化界面

echo.
echo ========================================
echo    ETF-ML Startup Wizard
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10+ was not found.
    echo Download: https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python environment check passed.

REM 检查并安装依赖
echo.
echo [INFO] Checking and installing dependencies...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1
pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo [OK] Dependencies are ready.

REM 启动 Flask 服务
echo.
echo ========================================
echo    Starting Flask backend service...
echo ========================================
echo.
echo URL: http://localhost:5000
echo Press Ctrl+C to stop.
echo.

python predict_api.py

pause
