#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户管理系统 - 安装验证脚本

用途: 验证依赖、数据库连接和基本功能
运行: python test_user_system.py
"""

import os
import sys
import importlib
from typing import Tuple

def print_header(text: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_success(text: str):
    """打印成功消息"""
    print(f"✓ {text}")

def print_error(text: str):
    """打印错误消息"""
    print(f"✗ {text}")

def print_warning(text: str):
    """打印警告消息"""
    print(f"⚠ {text}")

def check_dependencies() -> bool:
    """检查依赖库"""
    print_header("1. 检查依赖库")
    
    dependencies = {
        'flask': 'Flask (Web框架)',
        'flask_cors': 'Flask-CORS (跨域支持)',
        'pymysql': 'PyMySQL (MySQL驱动)',
        'dotenv': 'python-dotenv (配置管理)'
    }
    
    all_ok = True
    for module, name in dependencies.items():
        try:
            importlib.import_module(module)
            print_success(f"{name} 已安装")
        except ImportError:
            print_error(f"{name} 未安装")
            all_ok = False
    
    if not all_ok:
        print("\n请运行以下命令安装缺失的依赖:")
        print("  pip install -r requirements.txt")
        return False
    
    print("\n✓ 所有依赖库已安装")
    return True

def check_env_file() -> bool:
    """检查 .env 文件"""
    print_header("2. 检查配置文件")
    
    if os.path.exists('.env'):
        print_success(".env 文件存在")
        
        # 检查必要的配置项
        from dotenv import load_dotenv
        load_dotenv()
        
        host = os.getenv('host')
        port = os.getenv('port')
        username = os.getenv('username')
        database = os.getenv('database')
        
        if all([host, port, username, database]):
            print_success("所有必要的配置项都已设置")
            print(f"  Host: {host}")
            print(f"  Port: {port}")
            print(f"  Username: {username}")
            print(f"  Database: {database}")
            return True
        else:
            print_error("配置项不完整，请检查 .env 文件")
            print("  必要的配置项: host, port, username, database")
            return False
    else:
        print_warning(".env 文件不存在")
        print("  请复制 .env.example 到 .env 并修改配置:")
        print("  cp .env.example .env")
        return False

def check_database_connection() -> Tuple[bool, str]:
    """检查数据库连接"""
    print_header("3. 检查数据库连接")
    
    try:
        from user import UserManager, load_config
        
        config = load_config()
        user_manager = UserManager(config)
        
        if user_manager.connect():
            print_success("数据库连接成功")
            user_manager.disconnect()
            return True, "数据库连接正常"
        else:
            print_error("数据库连接失败")
            print("  请检查:")
            print("    1. MySQL 服务是否已启动")
            print("    2. .env 中的数据库配置是否正确")
            print("    3. 数据库用户名和密码是否正确")
            return False, "数据库连接失败"
    
    except Exception as e:
        print_error(f"检查数据库时出错: {e}")
        return False, str(e)

def check_user_module() -> bool:
    """检查用户模块"""
    print_header("4. 检查用户管理模块")
    
    try:
        from user import UserManager, load_config
        print_success("user.py 模块可以正常导入")
        
        # 检查主要方法
        methods = [
            'connect',
            'create_user_table',
            'create_user',
            'verify_user',
            'get_user_info',
            'update_user',
            'change_password',
            'list_users',
            'delete_user',
            'set_user_status'
        ]
        
        for method in methods:
            if hasattr(UserManager, method):
                print_success(f"  方法 '{method}' 存在")
            else:
                print_error(f"  方法 '{method}' 不存在")
                return False
        
        print("\n✓ 所有核心方法都存在")
        return True
    
    except ImportError as e:
        print_error(f"无法导入 user.py: {e}")
        return False
    except Exception as e:
        print_error(f"检查模块时出错: {e}")
        return False

def check_api_module() -> bool:
    """检查 API 模块"""
    print_header("5. 检查 API 模块")
    
    try:
        import user_api
        print_success("user_api.py 模块可以正常导入")
        
        # 检查 Flask 应用
        if hasattr(user_api, 'app'):
            print_success("Flask 应用已创建")
            
            # 检查路由
            routes = [
                '/api/users/register',
                '/api/users/login',
                '/api/users/info/<username>',
                '/api/users/update/<username>',
                '/api/users/change-password',
                '/api/users/list',
                '/api/users/delete/<username>',
                '/api/users/status/<username>',
                '/api/health'
            ]
            
            # 获取所有路由
            app_routes = set()
            for rule in user_api.app.url_map.iter_rules():
                app_routes.add(str(rule))
            
            print(f"  已注册 {len(app_routes)} 个路由")
            return True
        else:
            print_error("Flask 应用未找到")
            return False
    
    except ImportError as e:
        print_error(f"无法导入 user_api.py: {e}")
        return False
    except Exception as e:
        print_error(f"检查 API 模块时出错: {e}")
        return False

def test_basic_functions() -> bool:
    """测试基本功能"""
    print_header("6. 测试基本功能")
    
    try:
        from user import UserManager, load_config
        
        config = load_config()
        user_manager = UserManager(config)
        
        if not user_manager.connect():
            print_error("无法连接数据库，跳过功能测试")
            return False
        
        # 创建测试表
        if user_manager.create_user_table():
            print_success("用户表创建成功")
        else:
            print_warning("用户表创建失败（可能已存在）")
        
        # 测试用户创建
        test_username = "test_user_12345"
        test_password = "TestPass123"
        test_email = "test12345@example.com"
        
        # 先删除测试用户（如果存在）
        user_manager.delete_user(test_username)
        
        # 创建测试用户
        success, msg = user_manager.create_user({
            'username': test_username,
            'password': test_password,
            'email': test_email,
            'phone': '13800138888'
        })
        
        if success:
            print_success(f"测试用户创建成功: {test_username}")
        else:
            print_error(f"测试用户创建失败: {msg}")
            user_manager.disconnect()
            return False
        
        # 测试用户验证
        success, msg, user_info = user_manager.verify_user(test_username, test_password)
        if success:
            print_success("用户验证成功")
        else:
            print_error(f"用户验证失败: {msg}")
            user_manager.disconnect()
            return False
        
        # 测试获取用户信息
        success, msg, user_info = user_manager.get_user_info(test_username)
        if success:
            print_success("获取用户信息成功")
        else:
            print_error(f"获取用户信息失败: {msg}")
            user_manager.disconnect()
            return False
        
        # 测试更新用户信息
        success, msg = user_manager.update_user(test_username, {
            'real_name': '测试用户'
        })
        if success:
            print_success("更新用户信息成功")
        else:
            print_error(f"更新用户信息失败: {msg}")
        
        # 清理测试用户
        user_manager.delete_user(test_username)
        print_success("测试用户已清理")
        
        user_manager.disconnect()
        return True
    
    except Exception as e:
        print_error(f"功能测试出错: {e}")
        return False

def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 16 + "用户管理系统 - 安装验证" + " " * 16 + "║")
    print("╚" + "=" * 58 + "╝")
    
    results = {}
    
    # 1. 检查依赖
    results['依赖库'] = check_dependencies()
    if not results['依赖库']:
        print("\n✗ 依赖库检查失败，无法继续")
        return 1
    
    # 2. 检查配置文件
    results['配置文件'] = check_env_file()
    if not results['配置文件']:
        print("\n⚠ 配置文件缺失，请先配置 .env")
        print("  cp .env.example .env")
        return 1
    
    # 3. 检查数据库连接
    db_ok, db_msg = check_database_connection()
    results['数据库连接'] = db_ok
    if not db_ok:
        print("\n✗ 数据库连接失败，无法继续")
        return 1
    
    # 4. 检查用户模块
    results['用户模块'] = check_user_module()
    
    # 5. 检查 API 模块
    results['API模块'] = check_api_module()
    
    # 6. 测试基本功能
    results['基本功能'] = test_basic_functions()
    
    # 总结
    print_header("验证总结")
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{check_name:20} : {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("\n✓ 所有检查已通过！系统已准备就绪。\n")
        print("后续步骤:")
        print("  1. 启动 API 服务: python user_api.py")
        print("  2. 访问健康检查: http://localhost:5000/api/health")
        print("  3. 查看文档: README.md 或 QUICKSTART.md")
        print()
        return 0
    else:
        print("\n✗ 有些检查未通过，请根据上面的错误信息修复问题。\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
