# ETF智能投资平台 - 快速入门

## 一、环境准备

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

主要依赖包括：
- Flask, Flask-CORS（Web框架）
- PyMySQL（数据库连接）
- NumPy, Pandas（数据处理）
- PyTorch（深度学习模型）
- python-dotenv（环境配置）

### 2. 数据库配置

`.env` 文件已包含数据库连接信息：
```
host=mysql6.sqlpub.com
port=3311
username=etf_scut
password=79n4MXNJGnNjDRre
database=etf_scut
```

数据库会在首次启动时自动创建用户表。

## 二、启动服务

### Windows 系统
双击运行 `start.bat`

或在命令行执行：
```bash
python predict_api.py
```

### Linux/Mac 系统
```bash
bash start.sh
```

或直接运行：
```bash
python3 predict_api.py
```

## 三、访问系统

启动成功后，在浏览器访问：
- 首页：http://localhost:5000
- 股票预测：http://localhost:5000/predict.html
- 风险评估：http://localhost:5000/risk.html
- 持股管理：http://localhost:5000/holdings.html（登录后可用）
- 登录注册：http://localhost:5000/login.html

## 四、功能使用

### 1. 用户注册/登录

**注册要求：**
- 用户名：4-20字符，只能包含字母、数字、下划线
- 密码：至少6字符
- 邮箱：可选，格式正确即可
- 手机号：可选，需符合中国大陆11位手机号格式

**登录：**
使用注册的用户名和密码登录即可。

### 2. 持股管理（新功能）

用户登录后，可以访问"持股管理"页面来管理自己的投资组合：

**主要功能：**
- ✅ 添加股票：输入股票代码（如000001.SZ）添加到持股列表
- ✅ 查看持股：显示所有持有的股票及其支持状态
- ✅ 快速分析：可直接从持股列表跳转到预测或风险评估
- ✅ 删除股票：从持股列表中删除股票

**股票支持状态：**
- 🟢 **可分析**：系统已训练模型，支持预测和风险分析
- 🔴 **待支持**：系统还未完成该股票的模型训练，目前无法进行分析（显示🔒图标）

**支持的股票代码格式：**
- 深圳证券交易所：`XXXXXX.SZ`（如：`000001.SZ`）
- 上海证券交易所：`XXXXXX.SH`（如：`600000.SH`）
- 北京交易所：`XXXXXX.BJ`（如：`832288.BJ`）

### 3. 股票预测

- 登录后访问"股票预测"
- 选择股票代码（支持26只ETF股票，或从持股列表快速选择）
- 设置预测参数（预测天数、历史天数等）
- 选择模型类型（GRU、Transformer或两者组合）
- 点击"开始预测"查看结果

### 4. 风险评估

- 登录后访问"风险评估"
- 选择分析模式（单只股票或投资组合）
- 输入股票代码和权重（或从持股列表快速选择）
- 设置风险参数
- 查看风险指标和优化建议

## 五、技术架构

### 后端
- **框架**：Flask
- **数据库**：MySQL
- **模型**：GRU、Transformer
- **用户管理**：基于本地数据库的用户认证系统

### 前端
- **技术**：原生JavaScript + HTML + CSS
- **组件化**：模块化组件设计
- **状态管理**：本地存储 + 用户会话管理
- **API通信**：RESTful API调用

### 模型目录
- `predict_model/GRU/`：GRU模型文件（26只股票，.pth格式）
- `predict_model/Transformer/`：Transformer模型文件（26只股票，.pth格式）
- `risk_model/`：风险评估模型（包括coefficient、convex、gcn三种方法）

## 六、API文档

### 用户管理API

#### 注册
```
POST /api/users/register
Content-Type: application/json

{
    "username": "user123",
    "password": "pass123",
    "email": "user@example.com",
    "phone": "13800138000",
    "real_name": "张三"
}
```

#### 登录
```
POST /api/users/login
Content-Type: application/json

{
    "username": "user123",
    "password": "pass123"
}
```

### 持股管理API

#### 获取支持的股票列表
```
GET /api/stocks/supported

Response:
{
    "code": 0,
    "message": "获取支持的股票列表成功",
    "data": ["000001.SZ", "000002.SZ", ...]
}
```

#### 获取用户持股列表
```
GET /api/users/holdings?username=user123

Response:
{
    "code": 0,
    "message": "获取用户持有股票成功",
    "data": [
        {"code": "000001.SZ", "supported": true},
        {"code": "999999.SZ", "supported": false}
    ]
}
```

#### 添加股票
```
POST /api/users/holdings/add
Content-Type: application/json

{
    "username": "user123",
    "stock_code": "000001.SZ"
}

Response:
{
    "code": 0,
    "message": "股票添加成功！",
    "data": null
}
```

#### 删除股票
```
POST /api/users/holdings/remove
Content-Type: application/json

{
    "username": "user123",
    "stock_code": "000001.SZ"
}
```

## 七、常见问题

### Q1: 启动失败？
- 检查Python环境和依赖是否安装完整
- 确认端口5000未被占用
- 查看终端错误信息

### Q2: 注册失败？
- 用户名：4-20字符，字母数字下划线
- 密码：至少6字符
- 邮箱和手机号为可选项

### Q3: 股票代码格式无效？
- 确保使用正确的格式：`XXXXXX.SZ` 或 `XXXXXX.SH`
- 示例：`000001.SZ`、`600000.SH`

### Q4: 添加的股票显示"待支持"？
- 这表示系统还未为该股票训练出模型
- 该股票暂时无法进行预测和风险分析
- 请选择"可分析"状态的股票进行分析

### Q5: 预测/风险评估失败？
- 确认股票显示"可分析"状态
- 检查模型文件是否存在于 `predict_model/` 目录
- 查看浏览器控制台错误信息

### Q6: 数据库连接失败？
- 检查 `.env` 文件中的数据库配置
- 确认数据库服务正常运行
- 验证网络连接

## 八、支持的股票列表

系统目前支持以下26只ETF股票的预测和分析：

```
000001.SZ  000002.SZ  000063.SZ  000100.SZ  000157.SZ
000301.SZ  000338.SZ  000408.SZ  000425.SZ  000538.SZ
000568.SZ  000596.SZ  000617.SZ  000625.SZ  000630.SZ
000651.SZ  000661.SZ  000708.SZ  000725.SZ  000768.SZ
000786.SZ  000800.SZ  000807.SZ  000858.SZ  000876.SZ
000895.SZ
```

更多股票的模型正在训练中，敬请期待！

## 九、开发者信息

- **项目名称**：ETF智能投资平台
- **开发团队**：SCUT
- **技术栈**：Flask + PyTorch + MySQL
- **版本**：v1.0
- **最后更新**：2026-03-04

---

**提示**：首次使用建议先注册账号，然后在"持股管理"页面添加你要分析的股票，接着就可以体验股票预测和风险评估功能了！

