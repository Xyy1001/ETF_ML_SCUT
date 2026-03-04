# 持股管理系统故障排除摘要

## 当前问题
- 股票代码可以成功添加并存储到数据库
- 但"我的持仓"UI 页面不显示已存储的股票

## 快速诊断（3步）

### 步骤1️⃣: 运行自动化测试
```bash
cd "E:\ETF SCUT\G-Web"
python test_holdings_system.py
```

此脚本将自动测试：
- ✅ API 服务器是否运行
- ✅ 支持的股票列表是否正确加载
- ✅ 用户持股 API 是否返回数据
- ✅ 添加/删除股票的端点是否正常
- ✅ 添加后是否能成功检索新数据

### 步骤2️⃣: 检查浏览器控制台
1. 打开网站 (`http://127.0.0.1:5000`)
2. 登录用户账户
3. 导航到"持股管理"
4. 按 `F12` 打开开发者工具 → **Console** 标签
5. 查看日志输出：
   - `用户信息: {...}` → 验证用户是否正确加载
   - `请求URL: /api/users/holdings?username=...` → 验证用户名传递
   - `API响应: {...}` → 验证服务器数据格式

### 步骤3️⃣: 检查后端服务器日志
查看运行 `python predict_api.py` 的窗口，搜索日志：
```
[持股管理] 获取持股列表 - 用户名: xxx
[持股管理] 数据库查询结果 - 成功: True
[持股管理] 最终返回数据: [...]
```

如果服务器日志中没有 `[持股管理]` 前缀的消息，说明前端没有正确调用 API。

## 常见问题速检

| 症状 | 可能原因 | 检查方法 |
|------|--------|--------|
| 页面显示空列表 | 数据库中用户的 `holdings` 为空或 NULL | 查数据库：`SELECT holdings FROM users WHERE username='xxx'` |
| 添加成功但刷新后消失 | 数据库没有实际保存 | 检查服务器日志的"更新结果" |
| API 返回 404 | 服务器出错 | 查看 Console 标签的错误信息，检查后端日志 |
| 列表有数据但显示 undefined | 数据格式不匹配 | 在 Console 中运行：`fetch('/api/users/holdings?username=xxx').then(r=>r.json()).then(d=>console.log(d))` |

## 完整诊断文档
详见 [HOLDINGS_DEBUGGING.md](HOLDINGS_DEBUGGING.md)

此文件包含：
- 详细的数据流追踪
- SQL 查询示例
- JavaScript 控制台测试命令
- 每个组件的预期日志输出

## 优先级行动项

### 🔴 立即检查
1. 后端服务器是否在运行 (`http://127.0.0.1:5000` 能访问)
2. 用户是否成功登录（页面右上角显示用户名）
3. 运行 `test_holdings_system.py` 查看 API 是否响应

### 🟡 如果自动化测试失败
1. 查看完整的错误信息
2. 查看 [HOLDINGS_DEBUGGING.md](HOLDINGS_DEBUGGING.md) 对应的症状部分
3. 按照指导进行手动验证

### 🟢 如果自动化测试通过
1. 在浏览器中打开页面
2. 按 F12 打开 Console
3. 重新加载页面并添加一只股票
4. 查看 Console 日志输出，确定卡在哪一步

## 数据库快速查询

```sql
-- 查看用户和持股
SELECT id, username, email, holdings FROM users 
WHERE username = '你的用户名';

-- 查看是否有股票数据表
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'etf_scut' 
AND TABLE_NAME LIKE 'stock%' 
LIMIT 10;

-- 查看某个股票数据表的结构
DESC stock_000001_SZ;
```

## 如何在 MySQL 工作台中运行：
1. 打开 MySQL 工作台
2. 连接到 `mysql6.sqlpub.com:3311`
3. 选择数据库 `etf_scut`
4. 复制上面的 SQL 并执行

---
**跟踪状态**: 持股管理功能已实现，诊断工具已添加，问题排查进行中

**最后更新**: 2026-03-04 16:30
