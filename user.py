#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户管理系统
- 创建用户表
- 添加新用户
- 验证用户（登录）
- 查询用户信息
- 更新用户信息
- 删除用户
"""

import os
import sys
import re
import hashlib
from datetime import datetime
from typing import Dict, Optional, List, Tuple

import pymysql
from dotenv import load_dotenv, dotenv_values


class UserManager:
    """用户管理类"""

    def __init__(self, config: Dict[str, str]):
        """初始化数据库连接"""
        self.host = config.get("host", "localhost")
        self.port = int(config.get("port", "3306"))
        self.username = config.get("username", "root")
        self.password = config.get("password", "")
        self.database = config.get("database", "etf_scut")
        
        self.conn = None
        self.cursor = None

    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.username,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                autocommit=True,
            )
            self.cursor = self.conn.cursor()
            print(f"✓ 成功连接数据库: {self.host}:{self.port}/{self.database}")
            return True
        except pymysql.Error as e:
            print(f"✗ 数据库连接失败: {e}")
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def create_user_table(self) -> bool:
        """创建用户表"""
        sql = """
        CREATE TABLE IF NOT EXISTS `users` (
            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
            username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
            password VARCHAR(255) NOT NULL COMMENT '密码（SHA256加密）',
            email VARCHAR(100) UNIQUE COMMENT '邮箱',
            phone VARCHAR(20) UNIQUE COMMENT '手机号',
            real_name VARCHAR(100) COMMENT '真实姓名',
            gender ENUM('M', 'F', 'O') DEFAULT 'O' COMMENT '性别：M=男 F=女 O=其他',
            age INT COMMENT '年龄',
            address VARCHAR(255) COMMENT '地址',
            id_number VARCHAR(20) UNIQUE COMMENT '身份证号',
            holdings LONGTEXT COMMENT '用户持有的股票（股票代码用逗号隔开）',
            status ENUM('active', 'inactive', 'banned') DEFAULT 'active' COMMENT '账户状态',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            last_login TIMESTAMP NULL COMMENT '最后登录时间',
            remark VARCHAR(255) COMMENT '备注',
            INDEX idx_username (username),
            INDEX idx_email (email),
            INDEX idx_phone (phone),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表'
        """
        try:
            self.cursor.execute(sql)
            print("✓ 用户表创建成功")
            return True
        except pymysql.Error as e:
            print(f"✗ 创建用户表失败: {e}")
            return False

    @staticmethod
    def hash_password(password: str) -> str:
        """密码加密（SHA256）"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """验证手机号格式（中国大陆）"""
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone))

    @staticmethod
    def validate_username(username: str) -> bool:
        """验证用户名格式（4-20字符，只包含字母、数字、下划线）"""
        pattern = r'^[a-zA-Z0-9_]{4,20}$'
        return bool(re.match(pattern, username))

    @staticmethod
    def validate_password(password: str) -> bool:
        """验证密码强度（至少6字符）"""
        return len(password) >= 6

    @staticmethod
    def validate_holdings(holdings: str) -> bool:
        """
        验证股票代码格式（以逗号分隔）
        格式：XXXXXX.SZ 或 XXXXXX.SH（6位数字+2位交易所代码）
        示例：000001.SZ,000002.SZ,600000.SH
        """
        if not holdings or not isinstance(holdings, str):
            return False
        
        # 去除空格
        holdings = holdings.replace(' ', '')
        
        # 分割股票代码
        codes = holdings.split(',')
        
        # 验证每个股票代码
        pattern = r'^[0-9]{6}\.(SZ|SH|BJ)$'
        for code in codes:
            if not code or not re.match(pattern, code.upper()):
                return False
        
        return True

    def create_user(self, user_data: Dict) -> Tuple[bool, str]:
        """
        创建新用户
        
        参数:
            user_data: 用户信息字典，包含以下字段：
                - username: 用户名（必填）
                - password: 密码（必填）
                - email: 邮箱（可选）
                - phone: 手机号（可选）
                - real_name: 真实姓名（可选）
                - gender: 性别（可选）
                - age: 年龄（可选）
                - address: 地址（可选）
                - id_number: 身份证号（可选）
                - remark: 备注（可选）
                注：holdings（用户持有股票）在用户设置中修改，注册时无需输入
        
        返回:
            (成功标志, 消息)
        """
        # 数据验证
        username = user_data.get('username', '').strip()
        password = user_data.get('password', '').strip()
        email = user_data.get('email', '').strip()
        phone = user_data.get('phone', '').strip()
        real_name = user_data.get('real_name', '').strip()
        gender = user_data.get('gender', 'O')
        age = user_data.get('age')
        address = user_data.get('address', '').strip()
        id_number = user_data.get('id_number', '').strip()
        remark = user_data.get('remark', '').strip()

        # 验证必填字段
        if not username:
            return False, "用户名不能为空"
        
        if not password:
            return False, "密码不能为空"

        # 验证用户名格式
        if not self.validate_username(username):
            return False, "用户名格式无效（4-20字符，只能包含字母、数字、下划线）"

        # 验证密码强度
        if not self.validate_password(password):
            return False, "密码长度不足（至少6字符）"

        # 验证邮箱格式
        if email and not self.validate_email(email):
            return False, "邮箱格式无效"

        # 验证手机号格式
        if phone and not self.validate_phone(phone):
            return False, "手机号格式无效（请输入中国大陆11位手机号）"

        # 验证性别字段
        if gender not in ['M', 'F', 'O']:
            gender = 'O'

        # 验证年龄
        if age:
            try:
                age = int(age)
                if age < 0 or age > 150:
                    return False, "年龄不合法"
            except ValueError:
                return False, "年龄必须为整数"

        # 加密密码
        hashed_password = self.hash_password(password)

        # 构建SQL语句
        sql = """
        INSERT INTO users (
            username, password, email, phone, real_name, 
            gender, age, address, id_number, remark
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        try:
            self.cursor.execute(sql, (
                username,
                hashed_password,
                email if email else None,
                phone if phone else None,
                real_name if real_name else None,
                gender,
                age if age else None,
                address if address else None,
                id_number if id_number else None,
                remark if remark else None
            ))
            print(f"✓ 用户 '{username}' 创建成功")
            return True, f"用户 '{username}' 创建成功"
        except pymysql.IntegrityError as e:
            error_msg = str(e)
            if 'username' in error_msg:
                return False, "用户名已存在"
            elif 'email' in error_msg:
                return False, "邮箱已被注册"
            elif 'phone' in error_msg:
                return False, "手机号已被注册"
            elif 'id_number' in error_msg:
                return False, "身份证号已被使用"
            else:
                return False, f"用户创建失败: {error_msg}"
        except pymysql.Error as e:
            return False, f"数据库错误: {e}"

    def verify_user(self, username: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        验证用户（登录）
        
        参数:
            username: 用户名
            password: 密码（明文）
        
        返回:
            (验证成功, 消息, 用户信息字典或None)
        """
        if not username or not password:
            return False, "用户名或密码不能为空", None

        hashed_password = self.hash_password(password)

        sql = "SELECT id, username, email, phone, real_name, status, created_at FROM users WHERE username = %s"

        try:
            self.cursor.execute(sql, (username,))
            result = self.cursor.fetchone()

            if not result:
                return False, "用户不存在", None

            user_id, user_name, email, phone, real_name, status, created_at = result

            # 检查账户状态
            if status == 'banned':
                return False, "账户已被禁用", None
            elif status == 'inactive':
                return False, "账户未激活", None

            # 验证密码
            sql_pwd = "SELECT password FROM users WHERE username = %s"
            self.cursor.execute(sql_pwd, (username,))
            pwd_result = self.cursor.fetchone()
            
            if pwd_result and pwd_result[0] == hashed_password:
                # 更新最后登录时间
                update_sql = "UPDATE users SET last_login = %s WHERE username = %s"
                self.cursor.execute(update_sql, (datetime.now(), username))

                user_info = {
                    'id': user_id,
                    'username': user_name,
                    'email': email,
                    'phone': phone,
                    'real_name': real_name,
                    'status': status,
                    'created_at': str(created_at)
                }
                return True, f"登录成功，欢迎 {user_name}", user_info
            else:
                return False, "密码错误", None

        except pymysql.Error as e:
            return False, f"数据库错误: {e}", None

    def get_user_info(self, username: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        获取用户信息
        
        参数:
            username: 用户名
        
        返回:
            (成功标志, 消息, 用户信息字典或None)
        """
        sql = """
        SELECT id, username, email, phone, real_name, gender, age, address, 
               id_number, holdings, status, created_at, updated_at, last_login, remark
        FROM users WHERE username = %s
        """

        try:
            self.cursor.execute(sql, (username,))
            result = self.cursor.fetchone()

            if not result:
                return False, "用户不存在", None

            user_info = {
                'id': result[0],
                'username': result[1],
                'email': result[2],
                'phone': result[3],
                'real_name': result[4],
                'gender': result[5],
                'age': result[6],
                'address': result[7],
                'id_number': result[8],
                'holdings': result[9],
                'status': result[10],
                'created_at': str(result[11]),
                'updated_at': str(result[12]),
                'last_login': str(result[13]) if result[13] else None,
                'remark': result[14]
            }
            return True, "获取用户信息成功", user_info

        except pymysql.Error as e:
            return False, f"数据库错误: {e}", None

    def update_user(self, username: str, update_data: Dict) -> Tuple[bool, str]:
        """
        更新用户信息
        
        参数:
            username: 用户名
            update_data: 需要更新的字段字典（包括 holdings）
                - holdings: 用户持有的股票，以逗号分隔的股票代码
        
        返回:
            (成功标志, 消息)
        """
        allowed_fields = {
            'email': 'email',
            'phone': 'phone',
            'real_name': 'real_name',
            'gender': 'gender',
            'age': 'age',
            'address': 'address',
            'holdings': 'holdings',
            'remark': 'remark'
        }

        # 验证邮箱
        if 'email' in update_data and update_data['email']:
            if not self.validate_email(update_data['email']):
                return False, "邮箱格式无效"

        # 验证手机号
        if 'phone' in update_data and update_data['phone']:
            if not self.validate_phone(update_data['phone']):
                return False, "手机号格式无效"

        # 验证 holdings 格式
        if 'holdings' in update_data and update_data['holdings']:
            if not self.validate_holdings(update_data['holdings']):
                return False, "股票代码格式无效（请用逗号分隔，示例：000001.SZ,000002.SZ）"

        # 构建动态SQL
        set_clause = []
        params = []
        
        for key, value in update_data.items():
            if key in allowed_fields and value is not None:
                set_clause.append(f"{allowed_fields[key]} = %s")
                params.append(value)

        if not set_clause:
            return False, "没有有效的更新字段"

        params.append(username)
        sql = f"UPDATE users SET {', '.join(set_clause)} WHERE username = %s"

        try:
            self.cursor.execute(sql, params)
            if self.cursor.rowcount == 0:
                return False, "用户不存在"
            print(f"✓ 用户 '{username}' 信息更新成功")
            return True, f"用户 '{username}' 信息更新成功"
        except pymysql.IntegrityError as e:
            if 'email' in str(e):
                return False, "邮箱已被注册"
            elif 'phone' in str(e):
                return False, "手机号已被注册"
            return False, f"更新失败: 数据重复"
        except pymysql.Error as e:
            return False, f"数据库错误: {e}"

    def change_password(self, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        更改密码
        
        参数:
            username: 用户名
            old_password: 旧密码
            new_password: 新密码
        
        返回:
            (成功标志, 消息)
        """
        # 验证新密码强度
        if not self.validate_password(new_password):
            return False, "新密码强度不足（至少8字符，必须包含字母和数字）"

        # 验证旧密码
        success, msg, _ = self.verify_user(username, old_password)
        if not success:
            return False, "旧密码错误"

        hashed_new_password = self.hash_password(new_password)

        sql = "UPDATE users SET password = %s WHERE username = %s"

        try:
            self.cursor.execute(sql, (hashed_new_password, username))
            print(f"✓ 用户 '{username}' 密码修改成功")
            return True, "密码修改成功"
        except pymysql.Error as e:
            return False, f"数据库错误: {e}"

    def list_users(self, page: int = 1, page_size: int = 10) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        列出所有用户（分页）
        
        参数:
            page: 页码（从1开始）
            page_size: 每页数量
        
        返回:
            (成功标志, 消息, 用户列表)
        """
        offset = (page - 1) * page_size

        sql = """
        SELECT id, username, email, phone, real_name, status, created_at 
        FROM users LIMIT %s, %s
        """

        try:
            self.cursor.execute(sql, (offset, page_size))
            results = self.cursor.fetchall()

            users = []
            for result in results:
                user = {
                    'id': result[0],
                    'username': result[1],
                    'email': result[2],
                    'phone': result[3],
                    'real_name': result[4],
                    'status': result[5],
                    'created_at': str(result[6])
                }
                users.append(user)

            # 获取总数
            self.cursor.execute("SELECT COUNT(*) FROM users")
            total = self.cursor.fetchone()[0]

            return True, f"获取第 {page} 页用户成功，总共 {total} 个用户", users

        except pymysql.Error as e:
            return False, f"数据库错误: {e}", None

    def delete_user(self, username: str) -> Tuple[bool, str]:
        """
        删除用户
        
        参数:
            username: 用户名
        
        返回:
            (成功标志, 消息)
        """
        sql = "DELETE FROM users WHERE username = %s"

        try:
            self.cursor.execute(sql, (username,))
            if self.cursor.rowcount == 0:
                return False, "用户不存在"
            print(f"✓ 用户 '{username}' 删除成功")
            return True, f"用户 '{username}' 删除成功"
        except pymysql.Error as e:
            return False, f"数据库错误: {e}"

    def set_user_status(self, username: str, status: str) -> Tuple[bool, str]:
        """
        设置用户状态
        
        参数:
            username: 用户名
            status: 状态（active/inactive/banned）
        
        返回:
            (成功标志, 消息)
        """
        if status not in ['active', 'inactive', 'banned']:
            return False, "无效的状态值"

        sql = "UPDATE users SET status = %s WHERE username = %s"

        try:
            self.cursor.execute(sql, (status, username))
            if self.cursor.rowcount == 0:
                return False, "用户不存在"
            status_text = {'active': '激活', 'inactive': '未激活', 'banned': '禁用'}
            print(f"✓ 用户 '{username}' 已设置为 {status_text.get(status)}")
            return True, f"用户状态已更新为 {status_text.get(status)}"
        except pymysql.Error as e:
            return False, f"数据库错误: {e}"

    def get_user_holdings(self, username: str) -> Tuple[bool, str, Optional[List[str]]]:
        """
        获取用户持有的股票列表
        
        参数:
            username: 用户名
        
        返回:
            (成功标志, 消息, 股票代码列表)
        """
        sql = "SELECT holdings FROM users WHERE username = %s"
        
        try:
            self.cursor.execute(sql, (username,))
            result = self.cursor.fetchone()
            
            if not result:
                return False, "用户不存在", None
            
            holdings_str = result[0]
            
            # 如果没有股票，返回空列表
            if not holdings_str:
                return True, "获取用户持有股票成功", []
            
            # 分割股票代码
            holdings_list = [code.strip().upper() for code in holdings_str.split(',') if code.strip()]
            
            return True, "获取用户持有股票成功", holdings_list
        
        except pymysql.Error as e:
            return False, f"数据库错误: {e}", None

    def update_user_holdings(self, username: str, holdings: str) -> Tuple[bool, str]:
        """
        更新用户持有的股票
        
        参数:
            username: 用户名
            holdings: 股票代码字符串，以逗号分隔（示例：000001.SZ,000002.SZ）
                     若要清空持有股票，传入空字符串或 None
        
        返回:
            (成功标志, 消息)
        """
        # 如果 holdings 为 None 或空字符串，设置为 NULL
        if not holdings or not holdings.strip():
            holdings = None
        else:
            # 验证格式
            if not self.validate_holdings(holdings):
                return False, "股票代码格式无效（请用逗号分隔，示例：000001.SZ,000002.SZ）"
            
            # 规格化：去除空格，转换为大写
            holdings = ','.join([code.strip().upper() for code in holdings.split(',') if code.strip()])
        
        sql = "UPDATE users SET holdings = %s WHERE username = %s"
        
        try:
            self.cursor.execute(sql, (holdings, username))
            
            if self.cursor.rowcount == 0:
                return False, "用户不存在"
            
            if holdings:
                print(f"✓ 用户 '{username}' 的股票已更新为: {holdings}")
                return True, f"用户持有股票已更新为: {holdings}"
            else:
                print(f"✓ 用户 '{username}' 的股票已清空")
                return True, "用户持有股票已清空"
        
        except pymysql.Error as e:
            return False, f"数据库错误: {e}"


def load_config(env_path: str = '.env') -> Dict[str, str]:
    """加载数据库配置"""
    candidate_paths = []
    if env_path:
        candidate_paths.append(env_path)
        if not os.path.isabs(env_path):
            candidate_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), env_path))
    candidate_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

    file_env = {}

    for path in candidate_paths:
        if path and os.path.exists(path):
            file_env = {k: v for k, v in dotenv_values(path).items() if v is not None}
            load_dotenv(path, override=False)
            break

    def _get_conf(*keys: str, default: str = '') -> str:
        for key in keys:
            value = file_env.get(key)
            if value:
                return value
        for key in keys:
            value = os.getenv(key)
            if value:
                return value
        return default
    
    config = {
        'host': _get_conf('DB_HOST', 'host', default='localhost'),
        'port': _get_conf('DB_PORT', 'port', default='3306'),
        'username': _get_conf('DB_USERNAME', 'username', default='root'),
        'password': _get_conf('DB_PASSWORD', 'password', default=''),
        'database': _get_conf('DB_NAME', 'database', default='etf_scut'),
    }
    return config


def main():
    """主函数 - 演示用户管理功能"""
    config = load_config()
    user_manager = UserManager(config)

    if not user_manager.connect():
        sys.exit(1)

    # 创建用户表
    user_manager.create_user_table()

    # 交互式菜单
    while True:
        print("\n========== 用户管理系统 ==========")
        print("1. 创建新用户")
        print("2. 用户登录")
        print("3. 获取用户信息")
        print("4. 更新用户信息")
        print("5. 修改密码")
        print("6. 列出所有用户")
        print("7. 删除用户")
        print("8. 设置用户状态")
        print("9. 查看用户持有股票")
        print("10. 修改用户持有股票")
        print("0. 退出")
        print("==================================")

        choice = input("请选择操作（0-10）: ").strip()

        if choice == '1':  # 创建用户
            print("\n--- 创建新用户 ---")
            user_data = {}
            user_data['username'] = input("用户名（4-20字符，字母数字下划线）: ").strip()
            user_data['password'] = input("密码（至少8字符，包含字母和数字）: ").strip()
            user_data['email'] = input("邮箱（可选）: ").strip()
            user_data['phone'] = input("手机号（可选）: ").strip()
            user_data['real_name'] = input("真实姓名（可选）: ").strip()
            user_data['remark'] = input("备注（可选）: ").strip()

            success, msg = user_manager.create_user(user_data)
            print(f"{'✓' if success else '✗'} {msg}\n")

        elif choice == '2':  # 登录
            print("\n--- 用户登录 ---")
            username = input("用户名: ").strip()
            password = input("密码: ").strip()
            success, msg, user_info = user_manager.verify_user(username, password)
            print(f"{'✓' if success else '✗'} {msg}")
            if success:
                print(f"用户信息: {user_info}\n")

        elif choice == '3':  # 获取用户信息
            print("\n--- 获取用户信息 ---")
            username = input("用户名: ").strip()
            success, msg, user_info = user_manager.get_user_info(username)
            print(f"{'✓' if success else '✗'} {msg}")
            if success:
                for key, value in user_info.items():
                    print(f"  {key}: {value}")
                print()

        elif choice == '4':  # 更新用户信息
            print("\n--- 更新用户信息 ---")
            username = input("用户名: ").strip()
            update_data = {}
            update_data['email'] = input("新邮箱（留空则不更新）: ").strip()
            update_data['phone'] = input("新手机号（留空则不更新）: ").strip()
            update_data['real_name'] = input("新真实姓名（留空则不更新）: ").strip()
            
            # 移除空值
            update_data = {k: v for k, v in update_data.items() if v}
            
            success, msg = user_manager.update_user(username, update_data)
            print(f"{'✓' if success else '✗'} {msg}\n")

        elif choice == '5':  # 修改密码
            print("\n--- 修改密码 ---")
            username = input("用户名: ").strip()
            old_password = input("旧密码: ").strip()
            new_password = input("新密码: ").strip()
            success, msg = user_manager.change_password(username, old_password, new_password)
            print(f"{'✓' if success else '✗'} {msg}\n")

        elif choice == '6':  # 列出所有用户
            print("\n--- 用户列表 ---")
            page = int(input("请输入页码（默认1）: ").strip() or "1")
            success, msg, users = user_manager.list_users(page=page)
            print(f"{'✓' if success else '✗'} {msg}")
            if success:
                for user in users:
                    print(f"  {user['username']:15} | {user['email']:25} | {user['status']:10}")
                print()

        elif choice == '7':  # 删除用户
            print("\n--- 删除用户 ---")
            username = input("用户名: ").strip()
            confirm = input(f"确认删除用户 '{username}'？(y/n): ").strip().lower()
            if confirm == 'y':
                success, msg = user_manager.delete_user(username)
                print(f"{'✓' if success else '✗'} {msg}\n")

        elif choice == '8':  # 设置用户状态
            print("\n--- 设置用户状态 ---")
            username = input("用户名: ").strip()
            print("状态选项: active(激活)  inactive(未激活)  banned(禁用)")
            status = input("请输入状态: ").strip()
            success, msg = user_manager.set_user_status(username, status)
            print(f"{'✓' if success else '✗'} {msg}\n")

        elif choice == '9':  # 查看用户持有股票
            print("\n--- 查看用户持有股票 ---")
            username = input("用户名: ").strip()
            success, msg, holdings = user_manager.get_user_holdings(username)
            print(f"{'✓' if success else '✗'} {msg}")
            if success and holdings:
                print(f"  持有股票: {', '.join(holdings)}\n")
            elif success:
                print("  该用户暂未持有任何股票\n")

        elif choice == '10':  # 修改用户持有股票
            print("\n--- 修改用户持有股票 ---")
            username = input("用户名: ").strip()
            print("输入股票代码，以逗号分隔（示例：000001.SZ,000002.SZ,600000.SH）")
            print("清空所有股票请直接按 Enter")
            holdings = input("股票代码: ").strip()
            success, msg = user_manager.update_user_holdings(username, holdings)
            print(f"{'✓' if success else '✗'} {msg}\n")

        elif choice == '0':  # 退出
            print("退出系统...")
            break

        else:
            print("无效的选择，请重试\n")

    user_manager.disconnect()
    print("✓ 程序已退出")


if __name__ == '__main__':
    main()