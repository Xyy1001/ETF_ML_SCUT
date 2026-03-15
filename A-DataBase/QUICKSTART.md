# 用户管理系统 - 快速开始指南

## 5 分钟快速开始

### 步骤 1: 安装依赖

```bash
pip install pymysql python-dotenv flask flask-cors
```

### 步骤 2: 配置 .env 文件

在项目根目录创建 `.env` 文件（如果不存在），内容如下：

```env
host=localhost
port=3306
username=root
password=your_password
database=etf_scut
TUSHARE_TOKEN=your_token
```

### 步骤 3: 运行用户管理系统

**方式 1: 交互式菜单**（手动操作）

```bash
cd A-DataBase
python user.py
```

然后按照菜单提示操作。

**方式 2: API 服务**（供前端调用）

```bash
cd A-DataBase
python user_api.py
```

服务启动后，访问 http://localhost:5000/api/health 验证服务是否运行。

---

## 常用操作示例

### 创建新用户（Python）

```python
from user import UserManager, load_config

config = load_config()
um = UserManager(config)
um.connect()
um.create_user_table()

# 创建用户
success, msg = um.create_user({
    'username': 'john_doe',
    'password': 'MyPassword123',
    'email': 'john@example.com',
    'phone': '13800138000'
})
print(msg)

um.disconnect()
```

### 用户登录（Python）

```python
from user import UserManager, load_config

config = load_config()
um = UserManager(config)
um.connect()

success, msg, user_info = um.verify_user('john_doe', 'MyPassword123')
if success:
    print(f"登录成功! 欢迎 {user_info['real_name']}")
    print(f"邮箱: {user_info['email']}")
else:
    print(f"登录失败: {msg}")

um.disconnect()
```

### 注册用户（前端 JavaScript）

```javascript
async function registerUser() {
    const response = await fetch('/api/users/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: 'john_doe',
            password: 'MyPassword123',
            email: 'john@example.com',
            phone: '13800138000',
            real_name: '约翰'
        })
    });

    const data = await response.json();
    if (data.code === 0) {
        alert('注册成功');
    } else {
        alert('注册失败: ' + data.message);
    }
}
```

### 用户登录（前端 JavaScript）

```javascript
async function loginUser() {
    const response = await fetch('/api/users/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: 'john_doe',
            password: 'MyPassword123'
        })
    });

    const data = await response.json();
    if (data.code === 0) {
        console.log('登录成功:', data.data);
        // 保存用户信息到 localStorage
        localStorage.setItem('user', JSON.stringify(data.data));
    } else {
        alert('登录失败: ' + data.message);
    }
}
```

### 获取用户信息（前端 JavaScript）

```javascript
async function getUserInfo(username) {
    const response = await fetch(`/api/users/info/${username}`);
    const data = await response.json();
    
    if (data.code === 0) {
        console.log('用户信息:', data.data);
    } else {
        alert('获取失败: ' + data.message);
    }
}
```

### 更新用户信息（前端 JavaScript）

```javascript
async function updateUserInfo(username) {
    const response = await fetch(`/api/users/update/${username}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            email: 'newemail@example.com',
            phone: '13900139000',
            real_name: '约翰·迪恩'
        })
    });

    const data = await response.json();
    alert(data.message);
}
```

### 修改密码（前端 JavaScript）

```javascript
async function changePassword() {
    const response = await fetch('/api/users/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: 'john_doe',
            old_password: 'MyPassword123',
            new_password: 'NewPassword456'
        })
    });

    const data = await response.json();
    alert(data.message);
}
```

---

## API 端点速查

| 操作 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 注册 | POST | `/api/users/register` | 创建新用户 |
| 登录 | POST | `/api/users/login` | 用户认证 |
| 查询 | GET | `/api/users/info/<username>` | 获取用户信息 |
| 更新 | PUT | `/api/users/update/<username>` | 更新用户信息 |
| 改密 | POST | `/api/users/change-password` | 修改密码 |
| 列表 | GET | `/api/users/list?page=1&page_size=10` | 分页获取用户 |
| 删除 | DELETE | `/api/users/delete/<username>` | 删除用户 |
| 状态 | PUT | `/api/users/status/<username>` | 设置用户状态 |
| 检查 | GET | `/api/health` | 服务健康检查 |

---

## 验证规则速查

| 字段 | 要求 | 示例 |
|------|------|------|
| 用户名 | 4-20字符，[a-zA-Z0-9_] | `john_123` |
| 密码 | 8+字符，含字母和数字 | `Pass123` |
| 邮箱 | 标准邮箱格式 | `user@example.com` |
| 手机号 | 中国11位手机号 | `13800138000` |

---

## 常见错误排查

### 连接失败
```
✗ 数据库连接失败
```
**解决:**
1. 确认 MySQL 服务已启动
2. 检查 `.env` 中的数据库配置
3. 确认数据库用户名和密码正确

### 用户已存在
```
✗ 更新失败: 数据重复
```
**解决:**
- 邮箱/手机号/用户名已被使用，请更换

### 密码验证失败
```
✗ 密码强度不足（至少8字符，必须包含字母和数字）
```
**解决:**
- 密码必须至少 8 字符，且包含字母和数字
- 示例: `TestPass123` ✓ 而非 `test` ✗

---

## 数据库初始化

第一次运行时，系统会自动创建 `users` 表：

```bash
python user.py
# 然后选择菜单项 1 创建用户，会自动建表
```

或者手动初始化：

```python
from user import UserManager, load_config

config = load_config()
um = UserManager(config)
um.connect()
um.create_user_table()  # 创建表
um.disconnect()
```

---

## 完整的前端登录表单示例

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>用户登录</title>
    <style>
        body { font-family: Arial; max-width: 400px; margin: 50px auto; }
        form { border: 1px solid #ccc; padding: 20px; }
        input { display: block; width: 100%; margin: 10px 0; padding: 8px; }
        button { width: 100%; padding: 10px; background: #007bff; color: white; border: none; cursor: pointer; }
        button:hover { background: #0056b3; }
        .error { color: red; margin-top: 10px; }
        .success { color: green; margin-top: 10px; }
    </style>
</head>
<body>
    <h2>用户登录</h2>
    <form id="loginForm">
        <input type="text" id="username" placeholder="用户名" required>
        <input type="password" id="password" placeholder="密码" required>
        <button type="submit">登录</button>
        <div id="message"></div>
    </form>

    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const messageDiv = document.getElementById('message');

            try {
                const response = await fetch('/api/users/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();
                
                if (data.code === 0) {
                    messageDiv.innerHTML = `<p class="success">${data.message}</p>`;
                    // 保存用户信息
                    localStorage.setItem('currentUser', JSON.stringify(data.data));
                    // 重定向到主页
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1000);
                } else {
                    messageDiv.innerHTML = `<p class="error">${data.message}</p>`;
                }
            } catch (error) {
                messageDiv.innerHTML = `<p class="error">请求失败: ${error.message}</p>`;
            }
        });
    </script>
</body>
</html>
```

---

## 下一步

1. ✅ 阅读完整文档: [USER_MANAGEMENT_README.md](./USER_MANAGEMENT_README.md)
2. ✅ 启动 API 服务: `python user_api.py`
3. ✅ 集成前端表单
4. ✅ 测试用户注册和登录流程

---

## 获取帮助

有任何问题，请参考完整文档或查看源代码中的注释。

