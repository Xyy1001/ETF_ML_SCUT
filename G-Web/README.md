# ETF智能投资平台（G-Web）统一说明文档

本文件为项目总说明，整合了当前仓库中所有 Markdown 文档的核心信息，作为唯一优先阅读入口。

---

## 1. 项目概述

ETF 智能投资平台是一个基于 Flask + MySQL + PyTorch 的 Web 系统，提供三类核心能力：

1. 股票预测（GRU / Transformer）
2. 风险评估（coefficient / convex / gcn）
3. 用户与持仓管理（注册、登录、持股增删查）

当前前端采用原生 HTML + CSS + JavaScript，后端采用 Flask 提供 REST API。

---

## 2. 当前功能状态

### 已完成

- 用户系统：注册、登录、用户信息维护
- 持股管理：添加股票、删除股票、查看持股、支持状态展示
- 股票预测：支持模型调用与可视化页面
- 风险评估：支持多种模型方法

### 近期关键修复

- 密码最低长度已调整为 6 位
- 导航与页面路由已补齐（首页/登录/注册/持股页）
- 持股删除报错“用户名不能为空”已修复
- 持仓接口改造为“优先从登录态识别用户”，前端不再依赖显式传 `username`

---

## 3. 目录与关键文件

- `predict_api.py`：Flask 主入口与主要业务路由
- `user_routes.py`：用户与持股相关 API
- `user.py`：用户数据库访问与业务逻辑
- `holdings.html`：持股管理页面
- `predict.html`：预测页面
- `risk.html`：风险评估页面
- `js/utils.js`：HTTP 封装、用户状态、工具方法
- `js/components.js`：导航栏/页脚/Toast 等公共组件
- `test_holdings_system.py`：持仓链路测试脚本
- `_verify_db_and_auth.py`：数据库与认证连通性辅助检查

---

## 4. 环境与启动

## 4.1 安装依赖

```bash
pip install -r requirements.txt
```

## 4.2 配置数据库

项目使用 `.env` 中的 MySQL 配置。启动后会自动检查并创建用户表。

## 4.3 启动服务

Windows:

```bash
python predict_api.py
```

或双击 `start.bat`。

Linux / Mac:

```bash
bash start.sh
```

## 4.4 访问地址

- 首页：`http://127.0.0.1:5000/`
- 登录：`http://127.0.0.1:5000/login.html`
- 注册：`http://127.0.0.1:5000/register.html`
- 预测：`http://127.0.0.1:5000/predict.html`
- 风险：`http://127.0.0.1:5000/risk.html`
- 持股：`http://127.0.0.1:5000/holdings.html`

---

## 4.5 自动每日数据库更新（新增）

网站启动后（`python predict_api.py` 或 `start.sh` / `start.bat`），后端会在后台自动执行“日线增量更新 + 指标计算 + 入库”。

默认行为：

1. 启动服务时先执行一次更新检查
2. 之后按固定间隔轮询 Tushare 是否有新数据
3. 若有新数据，自动增量写入数据库并更新指标

可通过 `.env` 配置：

```env
# 是否启用自动更新（true/false）
AUTO_DAILY_UPDATE_ENABLED=true

# 启动服务时是否先跑一次
AUTO_DAILY_UPDATE_RUN_ON_START=true

# 轮询间隔（分钟）
AUTO_DAILY_UPDATE_INTERVAL_MINUTES=60

# 指标重算回看窗口（天）
AUTO_DAILY_UPDATE_LOOKBACK_DAYS=120

# 空表初次拉取起始日期
AUTO_DAILY_UPDATE_DEFAULT_START_DATE=20100101
```

说明：

1. 自动更新会读取当前 `.env` 的数据库配置和 `TUSHARE_TOKEN`
2. 仅会处理数据库中股票表（如 `000001.SZ`），不会影响其他业务表
3. 更新日志会在后端控制台输出，前缀为 `[AutoUpdate]`

---

## 5. 持股管理说明

## 5.1 支持格式

- `XXXXXX.SZ`
- `XXXXXX.SH`
- `XXXXXX.BJ`

示例：`000001.SZ`

## 5.2 支持状态

- 可分析：可直接跳转预测 / 风险评估
- 待支持：仅可保留或删除，暂不支持分析

## 5.3 存储方式

用户表 `users` 的 `holdings` 字段使用逗号分隔股票代码字符串。

---

## 6. API 摘要（统一响应结构）

响应基本结构：

```json
{
  "code": 0,
  "message": "...",
  "data": null,
  "timestamp": "ISO8601"
}
```

### 6.1 用户

- `POST /api/users/register`
- `POST /api/users/login`
- `POST /api/users/logout`

### 6.2 持股

- `GET /api/stocks/supported`
- `GET /api/users/holdings`
- `POST /api/users/holdings/add`
- `POST /api/users/holdings/remove`

### 6.3 用户识别机制（最新）

后端 `get_current_username()` 优先从请求头读取：

- `X-Current-User`

若请求头缺失，再兼容旧方式：

1. POST JSON 中的 `username`
2. Query 参数 `username`

前端 `js/utils.js` 已自动从登录态注入 `X-Current-User`，因此持股接口调用无需再显式传 `username`。

---

## 7. 常见问题与排查

## 7.1 服务启动失败

检查：

1. Python 环境是否正确（建议使用项目 conda 环境）
2. 依赖是否完整安装
3. 5000 端口是否被占用
4. `.env` 数据库配置是否可连通

## 7.2 持股页面不显示数据

检查顺序：

1. 是否已登录（右上角显示用户名）
2. 浏览器 Console 是否有请求失败
3. 后端日志是否出现 `[持股管理]` 前缀日志
4. 数据库 `users.holdings` 是否有值

## 7.3 添加/删除失败

重点检查：

- 股票代码格式是否正确
- 当前用户是否真实存在于数据库
- 请求是否带有 `X-Current-User`（前端默认会自动加）

---

## 8. 快速验证清单

启动后建议按此顺序验证：

1. 注册新用户
2. 登录并进入持股管理
3. 添加一只股票（如 `000001.SZ`）
4. 删除同一股票
5. 进入预测与风险页面做一次跳转验证
6. 运行 `python test_holdings_system.py` 检查持仓 API

---

## 9. 版本与演进建议

当前状态可用于本地开发与演示。后续建议：

1. 将“前端登录态”升级为“服务端 session/JWT 严格鉴权”
2. 为 `holdings` 拆分独立持仓表，替代逗号字符串
3. 增加持仓成本、数量、权重和收益追踪
4. 增加接口自动化测试与 CI
5. 增加生产部署方案（Gunicorn/Nginx、日志与监控）

---

## 10. 原文档归并来源

本统一文档归并自以下文件：

- `HOLDINGS_DEBUGGING.md`
- `HOLDINGS_FEATURE.md`
- `IMPLEMENTATION_SUMMARY.md`
- `QUICKSTART.md`
- `QUICK_TROUBLESHOOTING.md`
- `SYSTEM_STATUS.md`

如需历史过程、排障细节或阶段性记录，可继续参考上述文档。
