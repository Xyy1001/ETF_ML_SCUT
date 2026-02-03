#!/usr/bin/env python3
"""
快速测试脚本 - 本地运行网站交互测试
"""

import subprocess
import sys
import os
import time
import signal
import requests


def check_dependencies():
    """检查依赖是否安装"""
    print("🔍 检查依赖...")
    required_packages = ['flask', 'playwright', 'pytest']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} 未安装")
            missing.append(package)
    
    if missing:
        print(f"\n请安装缺失的包:")
        print(f"pip install {' '.join(missing)}")
        if 'playwright' in missing:
            print("playwright install chromium")
        return False
    return True


def start_flask_app():
    """启动Flask应用"""
    print("\n🚀 启动Flask应用...")
    
    # 进入G-Web目录
    web_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'G-Web')
    app_path = os.path.join(web_dir, 'app.py')
    
    if not os.path.exists(app_path):
        print(f"❌ 找不到 app.py: {app_path}")
        return None
    
    # 启动Flask
    process = subprocess.Popen(
        [sys.executable, app_path],
        cwd=web_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # 等待服务启动
    print("  等待服务启动...")
    for i in range(30):
        try:
            response = requests.get("http://localhost:5000")
            if response.status_code:
                print("  ✅ Flask应用已启动")
                return process
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    
    print("  ❌ Flask应用启动超时")
    process.kill()
    return None


def run_tests():
    """运行测试"""
    print("\n🧪 运行测试...")
    
    test_dir = os.path.dirname(__file__)
    
    result = subprocess.run(
        [
            sys.executable, '-m', 'pytest',
            test_dir,
            '-v',
            '--tb=short',
            '--html=test-results/report.html',
            '--self-contained-html'
        ],
        cwd=os.path.dirname(test_dir)
    )
    
    return result.returncode


def main():
    """主函数"""
    print("=" * 60)
    print("  ETF-ML 网站交互测试")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    flask_process = None
    
    try:
        # 启动Flask
        flask_process = start_flask_app()
        if not flask_process:
            print("\n❌ 无法启动Flask应用")
            sys.exit(1)
        
        # 运行测试
        exit_code = run_tests()
        
        # 显示结果
        print("\n" + "=" * 60)
        if exit_code == 0:
            print("  ✅ 所有测试通过!")
        else:
            print("  ❌ 测试失败")
        print("=" * 60)
        
        # 显示报告位置
        report_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'test-results',
            'report.html'
        )
        if os.path.exists(report_path):
            print(f"\n📊 测试报告: {os.path.abspath(report_path)}")
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被中断")
        sys.exit(1)
        
    finally:
        # 清理：停止Flask应用
        if flask_process:
            print("\n🛑 停止Flask应用...")
            flask_process.terminate()
            try:
                flask_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                flask_process.kill()


if __name__ == "__main__":
    main()
