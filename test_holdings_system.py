#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持股管理系统快速测试脚本
用于验证后端 API 功能是否正常
"""

import requests
import json
from datetime import datetime

# 配置
BASE_URL = "http://127.0.0.1:5000"
TEST_USERNAME = "testuser"  # 修改为实际用户名
TEST_STOCK_CODE = "000001.SZ"

def print_banner(title):
    """打印分隔标题"""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {title}")
    print(f"{'='*60}")

def test_supported_stocks():
    """测试获取支持的股票列表"""
    print_banner("测试1: 获取支持的股票列表")
    try:
        response = requests.get(f"{BASE_URL}/api/stocks/supported")
        result = response.json()
        
        if response.status_code == 200:
            print("✅ API 连接正常")
            if result.get('code') == 0:
                stocks = result.get('data', [])
                print(f"✅ 支持的股票数量: {len(stocks)}")
                print(f"   样本股票: {stocks[:5]}")
                return True
            else:
                print(f"❌ API 返回错误: {result.get('message')}")
                return False
        else:
            print(f"❌ HTTP 错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_get_holdings(username):
    """测试获取用户持股"""
    print_banner(f"测试2: 获取用户持股 (用户名: {username})")
    try:
        response = requests.get(f"{BASE_URL}/api/users/holdings", 
                              params={"username": username})
        result = response.json()
        
        if response.status_code == 200:
            print(f"✅ 请求成功")
            if result.get('code') == 0:
                holdings = result.get('data', [])
                print(f"✅ 获取到 {len(holdings)} 只股票")
                if holdings:
                    print(f"   持股列表: {[h.get('code') for h in holdings]}")
                    for h in holdings[:3]:
                        print(f"     - {h.get('code')}: 支持={h.get('supported')}")
                else:
                    print("   用户尚未持有任何股票")
                return holdings
            else:
                print(f"❌ API 返回错误: {result.get('message')}")
                return []
        else:
            print(f"❌ HTTP 错误: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return []

def test_add_holding(username, stock_code):
    """测试添加持股"""
    print_banner(f"测试3: 添加持股 (用户: {username}, 股票: {stock_code})")
    try:
        data = {
            "username": username,
            "stock_code": stock_code
        }
        response = requests.post(f"{BASE_URL}/api/users/holdings/add",
                               json=data)
        result = response.json()
        
        if response.status_code == 200:
            print(f"✅ 请求成功")
            if result.get('code') == 0:
                print(f"✅ 股票添加成功")
                print(f"   消息: {result.get('message')}")
                return True
            else:
                print(f"❌ 添加失败: {result.get('message')}")
                return False
        else:
            print(f"❌ HTTP 错误: {response.status_code}")
            print(f"   误: {result}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_remove_holding(username, stock_code):
    """测试删除持股"""
    print_banner(f"测试4: 删除持股 (用户: {username}, 股票: {stock_code})")
    try:
        data = {
            "username": username,
            "stock_code": stock_code
        }
        response = requests.post(f"{BASE_URL}/api/users/holdings/remove",
                               json=data)
        result = response.json()
        
        if response.status_code == 200:
            print(f"✅ 请求成功")
            if result.get('code') == 0:
                print(f"✅ 股票删除成功")
                print(f"   消息: {result.get('message')}")
                return True
            else:
                print(f"❌ 删除失败: {result.get('message')}")
                return False
        else:
            print(f"❌ HTTP 错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def run_full_test():
    """运行完整测试流程"""
    print("\n" + "🔍 开始持股管理系统测试".center(60, "="))
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"服务器地址: {BASE_URL}")
    print(f"测试用户: {TEST_USERNAME}")
    
    # 测试1: 支持的股票列表
    stocks_ok = test_supported_stocks()
    if not stocks_ok:
        print("\n❌ 后端服务器可能未启动，请先运行: python predict_api.py")
        return
    
    # 测试2: 获取当前持股
    print_banner("检查点: 获取当前持股状态")
    holdings_before = test_get_holdings(TEST_USERNAME)
    
    # 测试3: 添加持股
    stock_exists = any(h.get('code') == TEST_STOCK_CODE for h in holdings_before)
    if not stock_exists:
        add_ok = test_add_holding(TEST_USERNAME, TEST_STOCK_CODE)
        if add_ok:
            # 再次获取，验证是否成功添加
            print_banner("验证: 添加后重新获取持股")
            holdings_after = test_get_holdings(TEST_USERNAME)
            stock_exists_now = any(h.get('code') == TEST_STOCK_CODE 
                                  for h in holdings_after)
            if stock_exists_now:
                print(f"✅ 股票成功添加并能正确检索")
            else:
                print(f"⚠️  股票添加请求返回成功，但重新获取时未找到")
                print(f"   这可能指示前端-后端数据同步问题")
    else:
        print(f"ℹ️  股票 {TEST_STOCK_CODE} 已存在，跳过添加测试")
    
    # 测试4: 删除持股（可选）
    # test_remove_holding(TEST_USERNAME, TEST_STOCK_CODE)
    
    print("\n" + "🏁 测试完成".center(60, "="))
    print("如有问题，请查看 HOLDINGS_DEBUGGING.md 获取更详细的诊断指南\n")

if __name__ == "__main__":
    try:
        run_full_test()
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n\n⚠️  测试过程中出现异常: {e}")
