@echo off
chcp 65001 >nul
echo ================================================
echo   股票数据处理Web系统 - 启动脚本
echo ================================================
echo.

cd /d %~dp0

echo [1/4] 检查Python环境...
python --version
if errorlevel 1 (
    echo ❌ Python未安装或未添加到PATH
    pause
    exit /b 1
)
echo ✅ Python环境正常
echo.

echo [2/4] 检查依赖包...
python -c "import flask, pandas, tushare" 2>nul
if errorlevel 1 (
    echo ⚠️  缺少必要的依赖包，开始安装...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 依赖包安装失败
        pause
        exit /b 1
    )
)
echo ✅ 依赖包完整
echo.

echo [3/4] 检查配置文件...
if not exist "..\\.env" (
    echo ⚠️  未找到.env配置文件
    echo 请在项目根目录创建.env文件，添加以下内容：
    echo.
    echo TUSHARE_TOKEN=你的Token
    echo start_date=20230101
    echo end_date=20241231
    echo.
    pause
    exit /b 1
)
echo ✅ 配置文件存在
echo.

echo [4/4] 启动Flask服务器...
echo.
echo ================================================
echo   访问地址: http://127.0.0.1:5000
echo   按 Ctrl+C 停止服务器
echo ================================================
echo.

python app.py

pause
