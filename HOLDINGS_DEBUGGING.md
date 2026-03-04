# 持股管理页面调试指南

## 问题诊断步骤

### 1. 前端控制台日志
打开浏览器开发者工具（F12），切换到 Console 标签，查看：
- 用户信息是否正确加载
- API 请求 URL 是否正确
- API 响应数据格式是否正确

**预期日志：**
```
用户信息: {username: "testuser", id: 1, ...}
当前用户名: testuser
请求URL: /api/users/holdings?username=testuser
API响应: {code: 0, message: "获取用户持有股票成功", data: [...]}
当前持股: [{code: "000001.SZ", supported: true}, ...]
```

### 2. 后端服务器日志
查看运行 `predict_api.py` 的终端输出，看是否有以下日志：

```
[持股管理] 获取持股列表 - 用户名: testuser
[持股管理] 数据库查询结果 - 成功: True, 消息: 获取用户持有股票成功, 持股: ['000001.SZ']
[持股管理] 支持的股票列表: ['000001.SZ', '000002.SZ', ...]
[持股管理] 最终返回数据: [{'code': '000001.SZ', 'supported': True}, ...]
```

### 3. 检查清单

#### 3.1 用户数据
- [ ] 确认用户已登录
- [ ] 在浏览器 Console 中运行：`window.ETF.userManager.getUserData()`
- [ ] 确认返回的用户信息包含 `username` 字段

#### 3.2 数据库数据
- [ ] 登录数据库查看 users 表
- [ ] 检查该用户的 `holdings` 字段是否有数据
- [ ] 确认数据格式为：`000001.SZ,000002.SZ` （逗号分隔）

```sql
SELECT username, holdings FROM users WHERE username = 'testuser';
```

#### 3.3 API 调用
- [ ] 在浏览器 Console 中测试 API：
```javascript
fetch('/api/users/holdings?username=testuser')
  .then(r => r.json())
  .then(d => console.log(d))
```

#### 3.4 支持的股票列表
- [ ] 确认数据库中存在 `stock_XXXXXX_XX` 格式的表
- [ ] 测试 API：
```javascript
fetch('/api/stocks/supported')
  .then(r => r.json())
  .then(d => console.log(d))
```

## 常见问题和解决方案

### 问题1: "我的持仓"为空，但用户已登录

**可能原因：**
1. 数据库中该用户的 `holdings` 字段为 NULL 或空字符串
2. API 没有正确返回数据

**解决步骤：**
1. 查看后端日志中的 `[持股管理]` 信息
2. 检查数据库中用户的 holdings 值
3. 手动添加一只股票，查看是否能存储

### 问题2: 添加股票成功，但刷新后数据消失

**可能原因：**
1. 数据库连接中断
2. 数据库没有正确更新
3. 前端缓存问题

**解决步骤：**
1. 查看服务器日志中 `[持股管理] 更新结果` 的成功状态
2. 手动查询数据库确认数据是否存储
3. 清除浏览器缓存（Ctrl+Shift+Delete）

### 问题3: API 返回 404 或 500 错误

**可能原因：**
1. 用户不存在
2. 用户名未正确传递
3. 数据库连接失败

**解决步骤：**
1. 查看后端日志中的具体错误信息
2. 确认用户名是否正确
3. 检查数据库连接配置

### 问题4: 支持的股票列表为空

**可能原因：**
1. 数据库中没有 `stock_*` 表
2. `get_supported_stocks()` 函数出错

**解决步骤：**
1. 查看后端日志中的 `[持股管理] 支持的股票列表` 信息
2. 查询数据库检查是否存在股票数据表：
```sql
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'etf_scut' AND TABLE_NAME LIKE 'stock%';
```

## 数据流验证

### 添加股票的完整流程
```
前端：输入 000001.SZ，点击添加
  ↓
前端：POST /api/users/holdings/add {username: "testuser", stock_code: "000001.SZ"}
  ↓
后端日志：[持股管理] 添加股票 - 用户: testuser, 股票: 000001.SZ
  ↓
后端：获取当前持股列表 (可能为空)
  ↓
后端日志：[持股管理] 当前持股: None 或 []
  ↓
后端：构建新列表 "000001.SZ"
  ↓
后端：更新数据库
  ↓
后端日志：[持股管理] 更新结果 - 成功: True
  ↓
前端：收到成功响应，显示提示消息
  ↓
前端：调用 loadUserHoldings() 重新加载
  ↓
前端：GET /api/users/holdings?username=testuser
  ↓
后端日志：[持股管理] 获取持股列表 - 用户名: testuser
  ↓
后端：查询数据库
  ↓
后端日志：[持股管理] 数据库查询结果 - 成功: True, 持股: ['000001.SZ']
  ↓
前端：显示持股列表
```

## 快速测试步骤

### 测试1: 手动添加股票
```javascript
// 在浏览器 Console 中运行
fetch('/api/users/holdings/add', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    username: 'testuser',
    stock_code: '000001.SZ'
  })
})
.then(r => r.json())
.then(d => {
  console.log('添加结果:', d);
  // 添加成功后重新加载
  if (d.code === 0) {
    return fetch('/api/users/holdings?username=testuser');
  }
})
.then(r => r.json())
.then(d => console.log('持股列表:', d))
```

### 测试2: 检查数据库数据
```sql
-- 检查用户和持股
SELECT id, username, email, holdings FROM users WHERE username = 'testuser';

-- 检查是否有股票表
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'etf_scut' LIMIT 10;
```

## 性能优化建议

1. **缓存支持的股票列表**：已实现，首次加载后会缓存
2. **减少 API 调用**：已合并为单次调用
3. **批量操作**：支持在高级功能中实现
4. **数据库索引**：建议在 `users.username` 和 `users.holdings` 上添加索引

## 联系支持

如果问题仍未解决，请收集以下信息并提交：
1. 浏览器 Console 的完整输出
2. 后端服务器的完整日志
3. 用户名和添加的股票代码
4. 数据库中该用户的 holdings 字段值
5. 支持的股票列表 API 的返回值

---

**最后更新**：2026-03-04
