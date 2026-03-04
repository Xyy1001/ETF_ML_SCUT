#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一用户管理路由
- 供 predict_api.py 与 user_api.py 复用
"""

from datetime import datetime
from threading import Lock
import os
import re

from flask import Blueprint, jsonify, request

from user import UserManager, load_config


user_bp = Blueprint('user_api', __name__)

_manager: UserManager | None = None
_manager_lock = Lock()
_supported_stocks: list = None


def response(code: int, message: str, data=None):
    return {
        'code': code,
        'message': message,
        'data': data,
        'timestamp': datetime.now().isoformat()
    }


def get_user_manager(required: bool = True):
    global _manager

    if _manager is not None:
        return _manager

    with _manager_lock:
        if _manager is not None:
            return _manager

        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        config = load_config(env_path)
        manager = UserManager(config)
        connected = manager.connect()

        if not connected:
            if required:
                raise RuntimeError('数据库连接失败，请检查 .env 中数据库配置')
            return None

        manager.create_user_table()
        _manager = manager
        return _manager


def get_supported_stocks():
    """获取支持的股票列表（从数据库中检查是否存在日线数据表）"""
    global _supported_stocks
    
    if _supported_stocks is not None:
        return _supported_stocks
    
    supported = []
    
    try:
        manager = get_user_manager(required=False)
        if manager is None:
            print("获取支持股票列表失败：数据库未连接")
            return []
        
        # 查询数据库中所有的表名
        manager.cursor.execute("""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        """, (manager.database,))
        
        tables = manager.cursor.fetchall()
        
        # 过滤股票日线数据表
        # 假设股票表的命名规则为：stock_XXXXXX_SZ 或 stock_XXXXXX_SH
        for table in tables:
            table_name = table[0]
            # 检查是否是股票数据表（以stock_开头）
            if table_name.startswith('stock_'):
                # 提取股票代码 (从 stock_000001_SZ 提取 000001.SZ)
                parts = table_name[6:].rsplit('_', 1)  # 从 stock_ 后开始
                if len(parts) == 2:
                    code = parts[0]
                    exchange = parts[1].upper()
                    stock_code = f"{code}.{exchange}"
                    if stock_code not in supported:
                        supported.append(stock_code)
        
        supported.sort()
        _supported_stocks = supported
        
        if supported:
            print(f"从数据库中找到 {len(supported)} 只股票的日线数据")
        else:
            print("数据库中未找到股票日线数据表")
            
    except Exception as e:
        print(f"获取支持股票列表失败: {e}")
        _supported_stocks = []
    
    return _supported_stocks
    
    return supported


def get_current_username():
    """从请求中获取当前用户名（优先登录态，其次兼容旧参数）"""
    # 1) 优先从请求头获取（由前端登录态自动注入）
    username = request.headers.get('X-Current-User', '').strip()
    if username:
        return username

    # 2) 兼容：从POST body中获取
    if request.method == 'POST':
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        if username:
            return username
    
    # 3) 兼容：从查询参数中获取
    username = request.args.get('username', '').strip()
    if username:
        return username
    
    return None


@user_bp.route('/api/users/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify(response(1, '请求体不能为空')), 400

        manager = get_user_manager()
        success, msg = manager.create_user(data)
        return jsonify(response(0 if success else 1, msg)), 200 if success else 400
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        username = str(data.get('username', '')).strip()
        password = str(data.get('password', '')).strip()

        if not username or not password:
            return jsonify(response(1, '用户名和密码不能为空')), 400

        manager = get_user_manager()
        success, msg, user_info = manager.verify_user(username, password)
        return jsonify(response(0 if success else 1, msg, user_info if success else None)), 200 if success else 401
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/logout', methods=['POST'])
def logout():
    return jsonify(response(0, '已退出登录')), 200


@user_bp.route('/api/users/info', methods=['GET'])
def user_info():
    return jsonify(response(0, 'ok', None)), 200


@user_bp.route('/api/users/info/<username>', methods=['GET'])
def get_user_info(username):
    try:
        manager = get_user_manager()
        success, msg, user_info_data = manager.get_user_info(username)
        return jsonify(response(0 if success else 1, msg, user_info_data if success else None)), 200 if success else 404
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/update/<username>', methods=['PUT'])
def update_user(username):
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify(response(1, '请求体不能为空')), 400

        manager = get_user_manager()
        success, msg = manager.update_user(username, data)
        return jsonify(response(0 if success else 1, msg)), 200 if success else 400
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/change-password', methods=['POST'])
def change_password():
    try:
        data = request.get_json() or {}
        username = str(data.get('username', '')).strip()
        old_password = str(data.get('old_password', '')).strip()
        new_password = str(data.get('new_password', '')).strip()

        if not all([username, old_password, new_password]):
            return jsonify(response(1, '用户名、旧密码和新密码不能为空')), 400

        manager = get_user_manager()
        success, msg = manager.change_password(username, old_password, new_password)
        return jsonify(response(0 if success else 1, msg)), 200 if success else 400
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/list', methods=['GET'])
def list_users():
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        page = max(1, page)
        if page_size < 1 or page_size > 100:
            page_size = 10

        manager = get_user_manager()
        success, msg, users = manager.list_users(page=page, page_size=page_size)
        return jsonify(response(0 if success else 1, msg, users if success else [])), 200 if success else 400
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/delete/<username>', methods=['DELETE'])
def delete_user(username):
    try:
        manager = get_user_manager()
        success, msg = manager.delete_user(username)
        return jsonify(response(0 if success else 1, msg)), 200 if success else 404
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/status/<username>', methods=['PUT'])
def set_user_status(username):
    try:
        data = request.get_json() or {}
        status = str(data.get('status', '')).strip()

        if not status:
            return jsonify(response(1, '状态值不能为空')), 400

        manager = get_user_manager()
        success, msg = manager.set_user_status(username, status)
        return jsonify(response(0 if success else 1, msg)), 200 if success else 400
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/<username>/holdings', methods=['GET'])
def get_holdings(username):
    try:
        manager = get_user_manager()
        success, msg, holdings = manager.get_user_holdings(username)
        return jsonify(response(0 if success else 1, msg, holdings if success else [])), 200 if success else 404
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/<username>/holdings', methods=['PUT'])
def update_holdings(username):
    try:
        data = request.get_json() or {}
        if data is None:
            return jsonify(response(1, '请求体不能为空')), 400

        holdings = str(data.get('holdings', '')).strip()

        manager = get_user_manager()
        success, msg = manager.update_user_holdings(username, holdings)
        return jsonify(response(0 if success else 1, msg)), 200 if success else 400
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


# ==================== 持股管理路由（新增） ====================

@user_bp.route('/api/stocks/supported', methods=['GET'])
def get_supported_stocks_api():
    """获取支持分析的股票列表"""
    try:
        stocks = get_supported_stocks()
        return jsonify(response(0, '获取支持的股票列表成功', stocks)), 200
    except Exception as e:
        return jsonify(response(1, f'获取股票列表失败: {str(e)}', [])), 500


@user_bp.route('/api/users/holdings', methods=['GET'])
def get_user_holdings():
    """获取当前用户的持股列表"""
    try:
        username = get_current_username()
        print(f"[持股管理] 获取持股列表 - 用户名: {username}")
        
        if not username:
            print("[持股管理] 错误: 用户名为空")
            return jsonify(response(1, '用户名不能为空')), 400

        manager = get_user_manager()
        success, msg, holdings_list = manager.get_user_holdings(username)
        
        print(f"[持股管理] 数据库查询结果 - 成功: {success}, 消息: {msg}, 持股: {holdings_list}")
        
        if not success:
            return jsonify(response(1, msg, [])), 404
        
        # 构建持股对象列表，包含每只股票的支持状态
        supported_stocks = get_supported_stocks()
        print(f"[持股管理] 支持的股票列表: {supported_stocks}")
        
        holdings_data = []
        
        if holdings_list:
            for code in holdings_list:
                holdings_data.append({
                    'code': code,
                    'supported': code in supported_stocks
                })
        
        print(f"[持股管理] 最终返回数据: {holdings_data}")
        return jsonify(response(0, msg, holdings_data)), 200
    except Exception as e:
        print(f"[持股管理] 异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/holdings/raw', methods=['GET'])
def get_user_holdings_raw():
    """直接读取 users.holdings 字段并返回（不附带 supported 信息）。"""
    try:
        username = get_current_username()
        if not username:
            username = str(request.args.get('username', '')).strip()

        if not username:
            return jsonify(response(1, '用户名不能为空', {
                'username': '',
                'holdings': [],
                'holdings_text': ''
            })), 400

        manager = get_user_manager()
        success, msg, holdings_list = manager.get_user_holdings(username)

        if not success:
            return jsonify(response(1, msg, {
                'username': username,
                'holdings': [],
                'holdings_text': ''
            })), 404

        holdings = holdings_list if holdings_list else []
        return jsonify(response(0, msg, {
            'username': username,
            'holdings': holdings,
            'holdings_text': ','.join(holdings)
        })), 200
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}', {
            'username': '',
            'holdings': [],
            'holdings_text': ''
        })), 500


@user_bp.route('/api/users/holdings/add', methods=['POST'])
def add_user_holding():
    """添加股票到用户持股（支持批量添加）"""
    try:
        data = request.get_json() or {}
        username = get_current_username()
        
        # 支持单个股票代码（向后兼容）或多个股票代码
        stock_code_single = data.get('stock_code', '').strip().upper() if data.get('stock_code') else None
        stock_codes_list = data.get('stock_codes', [])
        
        # 整合成统一的列表
        if stock_code_single:
            stock_codes = [stock_code_single]
        elif isinstance(stock_codes_list, list):
            stock_codes = [str(code).strip().upper() for code in stock_codes_list if code]
        else:
            stock_codes = []
        
        print(f"[持股管理] 批量添加股票 - 用户: {username}, 股票: {stock_codes}")
        
        if not username:
            print("[持股管理] 错误: 用户名为空")
            return jsonify(response(1, '用户名不能为空')), 400
        
        if not stock_codes:
            print("[持股管理] 错误: 股票代码为空")
            return jsonify(response(1, '股票代码不能为空')), 400
        
        # 验证股票代码格式
        pattern = r'^[0-9]{6}\.(SZ|SH|BJ)$'
        invalid_codes = []
        valid_codes = []
        
        for code in stock_codes:
            if not re.match(pattern, code):
                invalid_codes.append(code)
            else:
                valid_codes.append(code)
        
        if invalid_codes:
            print(f"[持股管理] 错误: 股票代码格式无效 - {invalid_codes}")
            return jsonify(response(1, f'股票代码格式无效: {", ".join(invalid_codes)}')), 400
        
        manager = get_user_manager()
        
        # 获取当前持股列表
        success, msg, current_holdings = manager.get_user_holdings(username)
        
        print(f"[持股管理] 当前持股: {current_holdings}")
        
        if not success:
            print("[持股管理] 错误: 用户不存在")
            return jsonify(response(1, '用户不存在')), 404
        
        current_holdings_list = current_holdings if current_holdings else []
        
        # 检查哪些股票已存在，哪些是新的
        added_codes = []
        skipped_codes = []
        
        for code in valid_codes:
            if code in current_holdings_list:
                skipped_codes.append(code)
                print(f"[持股管理] 跳过已存在的股票 - {code}")
            else:
                added_codes.append(code)
        
        if not added_codes:
            print(f"[持股管理] 所有股票都已存在")
            return jsonify(response(1, '所有股票都已在持股列表中')), 400
        
        # 构建新的持股列表
        new_holdings_list = current_holdings_list + added_codes
        new_holdings = ','.join(new_holdings_list)
        
        print(f"[持股管理] 新的持股列表: {new_holdings}")
        
        # 更新数据库
        success, msg = manager.update_user_holdings(username, new_holdings)
        
        print(f"[持股管理] 更新结果 - 成功: {success}, 消息: {msg}")
        
        if success:
            result_data = {
                'added': added_codes,
                'skipped': skipped_codes,
                'total': len(new_holdings_list)
            }
            return jsonify(response(0, f'成功添加 {len(added_codes)} 只股票', result_data)), 200
        else:
            return jsonify(response(1, msg)), 400
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/users/holdings/remove', methods=['POST'])
def remove_user_holding():
    """删除用户持股中的股票"""
    try:
        data = request.get_json() or {}
        username = get_current_username()
        stock_code = str(data.get('stock_code', '')).strip().upper()
        
        if not username:
            return jsonify(response(1, '用户名不能为空')), 400
        
        if not stock_code:
            return jsonify(response(1, '股票代码不能为空')), 400
        
        manager = get_user_manager()
        
        # 获取当前持股列表
        success, msg, current_holdings = manager.get_user_holdings(username)
        
        if not success:
            return jsonify(response(1, '用户不存在')), 404
        
        # 检查是否存在
        if not current_holdings or stock_code not in current_holdings:
            return jsonify(response(1, '该股票不在持股列表中')), 400
        
        # 删除该股票
        new_holdings_list = [h for h in current_holdings if h != stock_code]
        new_holdings = ','.join(new_holdings_list) if new_holdings_list else ''
        
        # 更新数据库
        success, msg = manager.update_user_holdings(username, new_holdings)
        
        if success:
            return jsonify(response(0, '股票已删除')), 200
        else:
            return jsonify(response(1, msg)), 400
    
    except Exception as e:
        return jsonify(response(1, f'服务器错误: {str(e)}')), 500


@user_bp.route('/api/health', methods=['GET'])
def health():
    manager = get_user_manager(required=False)
    db_connected = manager is not None
    return jsonify({
        'code': 0,
        'message': 'API服务运行中',
        'data': {
            'db_connected': db_connected
        },
        'timestamp': datetime.now().isoformat()
    }), 200
