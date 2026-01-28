@echo off
chcp 65001
cls
echo ========================================
echo   ETF-ML展示系统启动中...
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖是否安装
echo [1/3] 检查依赖...
pip show flask >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在安装依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

REM 启动Flask服务
echo [2/3] 启动Flask服务...
echo.
echo ========================================
echo   服务启动成功！
echo   访问地址: http://localhost:5001
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

python app.py

pause
