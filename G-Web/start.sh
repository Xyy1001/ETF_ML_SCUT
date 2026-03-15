#!/bin/bash

# ==================== ETF-ML 预测系统启动脚本 ====================
# 这个脚本用于在 Linux/Mac 上启动 Flask 后端服务

echo ""
echo "========================================"
echo "    ETF-ML 预测系统启动向导"
echo "========================================"
echo ""

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python 3，请先安装 Python 3.8+"
    echo "安装命令 (Ubuntu/Debian): sudo apt-get install python3-pip"
    echo "安装命令 (macOS): brew install python3"
    exit 1
fi

echo "[✓] Python 环境检查通过"
python3 --version

# 检查并安装依赖
echo ""
echo "[正在检查依赖包...]

# 设置国内镜像源（可选）
# pip3 install -i https://pypi.tsinghua.edu.cn/simple -r requirements.txt

pip3 install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[错误] 依赖安装失败"
    exit 1
fi

echo "[✓] 依赖包安装/检查完成"

# 启动 Flask 服务
echo ""
echo "========================================"
echo "    启动 Flask 后端服务..."
echo "========================================"
echo ""
echo "服务地址: http://localhost:5000"
echo "按 Ctrl+C 停止服务"
echo ""

python3 predict_api.py
