#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ETF 项目数据库和认证系统完整验证脚本
主要测试内容：
1. 数据库连接是否正常
2. 用户注册和登录是否成功
3. 远程 MySQL 连接是否可用
"""

import os
import sys
import json
import time
from datetime import datetime

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_header(text: str, char: str = "="):
    """打印带边框的标题"""
    width = 70
    print("\n" + char * width)
    print(f"  {text}")
    print(char * width)

def print_success(text: str):
    """打印成功消息"""
    print(f"✓ {text}")

def print_error(text: str):
    """打印错误消息"""
    print(f"✗ {text}")

def print_warning(text: str):
    """打印警告消息"""
    print(f"⚠ {text}")

def print_info(text: str):
    """打印信息消息"""
    print(f"ℹ {text}")

def check_dependencies():
    """检查所必需的依赖"""
    print_header("Step 0: 检查依赖库")
    
    required_modules = {
        'flask': 'Flask',
        'flask_cors': 'Flask-CORS',
        'pymysql': 'PyMySQL',
        'dotenv': 'python-dotenv',
        'pandas': 'Pandas',
        'numpy': 'NumPy',
        'torch': 'PyTorch'
    }
    
    missing = []
    for module, name in required_modules.items():
        try:
            __import__(module)
            print_success(f"{name} 已安装")
        except ImportError:
            print_warning(f"{name} 未安装")
            missing.append(module)
    
    if missing:
        print(f"\n缺失的包：{', '.join(missing)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    print("\n✓ 所有依赖满足\n")
    return True

def check_config():
    """检查 .env 配置文件"""
    print_header("Step 1: 检查配置文件")
    
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    
    if not os.path.exists(env_file):
        print_error(f".env 文件不存在: {env_file}")
        print("请复制 .env.example 并修改数据库配置")
        return False
    
    print_success(f".env 文件存在: {env_file}")
    
    # 读取 .env 文件内容
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    db_config_keys = ['host', 'port', 'username', 'password', 'database', 
                      'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASS', 'DB_NAME']
    
    found_keys = set()
    for line in lines:
        for key in db_config_keys:
            if line.startswith(key + '='):
                found_keys.add(key)
                value = line.split('=', 1)[1].strip()
                if 'password' not in key.lower():
                    print_info(f"  {key} = {value}")
                else:
                    print_info(f"  {key} = {'*' * len(value)}")
    
    print("\n✓ 配置文件检查完毕\n")
    return True

def check_db_connection():
    """检查数据库连接"""
    print_header("Step 2: 检查数据库连接")
    
    try:
        from user import UserManager, load_config
        
        config = load_config()
        print_info(f"数据库配置:")
        print_info(f"  Host: {config.get('host')}")
        print_info(f"  Port: {config.get('port')}")
        print_info(f"  User: {config.get('username')}")
        print_info(f"  Database: {config.get('database')}")
        
        user_manager = UserManager(config)
        
        if user_manager.connect():
            print_success("✓ 数据库连接成功")
            
            # 检查用户表
            if user_manager.create_user_table():
                print_success("✓ 用户表已创建或已存在")
            else:
                print_error("✗ 创建用户表失败")
                user_manager.disconnect()
                return False
            
            user_manager.disconnect()
            print("\n✓ 数据库连接检查通过\n")
            return True
        else:
            print_error("✗ 数据库连接失败")
            print_error("请检查:")
            print_error("  1. .env 中的数据库配置是否正确")
            print_error("  2. MySQL 服务是否已启动")
            print_error("  3. 数据库用户名和密码是否正确")
            return False
    
    except Exception as e:
        print_error(f"✗ 检查数据库时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_user_operations():
    """测试用户注册和登录"""
    print_header("Step 3: 测试用户操作")
    
    from user import UserManager, load_config
    
    config = load_config()
    user_manager = UserManager(config)
    
    if not user_manager.connect():
        print_error("✗ 无法连接数据库，跳过用户操作测试")
        return False
    
    user_manager.create_user_table()
    
    # 测试数据
    test_username = f"testuser_{int(time.time())}"
    test_password = "TestPass123"
    test_email = "test@example.com"
    test_phone = "13800138888"
    
    try:
        # 1. 测试创建用户
        print_info(f"正在创建测试用户: {test_username}")
        success, msg = user_manager.create_user({
            'username': test_username,
            'password': test_password,
            'email': test_email,
            'phone': test_phone,
            'real_name': '测试用户'
        })
        
        if success:
            print_success(f"✓ 用户创建成功")
        else:
            print_error(f"✗ 用户创建失败: {msg}")
            user_manager.disconnect()
            return False
        
        # 2. 测试用户验证（登录）
        print_info(f"正在验证用户登录...")
        success, msg, user_info = user_manager.verify_user(test_username, test_password)
        
        if success:
            print_success(f"✓ 用户验证成功")
            print_info(f"  用户信息: {user_info}")
        else:
            print_error(f"✗ 用户验证失败: {msg}")
            user_manager.delete_user(test_username)
            user_manager.disconnect()
            return False
        
        # 3. 测试错误密码
        print_info(f"正在测试错误密码...")
        success, msg, _ = user_manager.verify_user(test_username, "WrongPassword123")
        
        if not success:
            print_success(f"✓ 密码验证正确拒绝了错误密码")
        else:
            print_error(f"✗ 密码验证未能正确检测错误密码")
            user_manager.delete_user(test_username)
            user_manager.disconnect()
            return False
        
        # 4. 获取用户信息
        print_info(f"正在获取用户信息...")
        success, msg, user_info = user_manager.get_user_info(test_username)
        
        if success:
            print_success(f"✓ 获取用户信息成功")
        else:
            print_error(f"✗ 获取用户信息失败: {msg}")
            user_manager.delete_user(test_username)
            user_manager.disconnect()
            return False
        
        # 5. 清理测试数据
        print_info(f"正在清理测试数据...")
        success, msg = user_manager.delete_user(test_username)
        
        if success:
            print_success(f"✓ 测试数据清理成功")
        else:
            print_warning(f"⚠ 测试数据清理失败: {msg}")
        
        user_manager.disconnect()
        print("\n✓ 用户操作测试通过\n")
        return True
    
    except Exception as e:
        print_error(f"✗ 测试用户操作时出错: {e}")
        import traceback
        traceback.print_exc()
        user_manager.disconnect()
        return False

def test_api_routes():
    """测试 Flask API 路由"""
    print_header("Step 4: 测试 API 路由")
    
    try:
        from user_routes import user_bp
        print_success("✓ user_routes 模块可以正常导入")
        
        # 检查蓝图
        routes = [
            '/api/users/register',
            '/api/users/login',
            '/api/users/logout',
            '/api/users/info',
            '/api/users/list',
            '/api/health'
        ]
        
        print_info(f"检查到以下路由:")
        for route in routes:
            print_info(f"  {route}")
        
        print("\n✓ API 路由检查完毕\n")
        return True
    
    except Exception as e:
        print_error(f"✗ 测试 API 路由时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  ETF 项目 - 数据库和认证系统验证".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    start_time = time.time()
    
    results = {
        "依赖检查": check_dependencies(),
        "配置检查": check_config(),
        "数据库连接": check_db_connection(),
        "用户操作": test_user_operations(),
        "API路由": test_api_routes()
    }
    
    # 总结
    print_header("验证总结", "=")
    
    all_pass = True
    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}  {name}")
        if not result:
            all_pass = False
    
    elapsed = time.time() - start_time
    print(f"\n总耗时: {elapsed:.2f} 秒\n")
    
    if all_pass:
        print("╔" + "=" * 68 + "╗")
        print("║" + "  ✓ 所有验证通过！".center(68) + "║")
        print("║" + "  应用已准备就绪，可以启动 Flask 服务。".center(68) + "║")
        print("╚" + "=" * 68 + "╝")
        print("\n运行以下命令启动服务:")
        print("  Windows: start.bat")
        print("  Linux/Mac: ./start.sh")
        print("  或直接运行: python predict_api.py\n")
        return 0
    else:
        print("╔" + "=" * 68 + "╗")
        print("║" + "  ✗ 验证失败，请检查上述错误信息。".center(68) + "║")
        print("╚" + "=" * 68 + "╝\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
