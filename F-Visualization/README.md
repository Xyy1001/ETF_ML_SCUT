# 股票数据处理Web系统

这是一个基于Flask的股票数据处理可视化Web应用，提供专业的股票搜索、选择和技术指标计算功能。

## 📁 文件结构

```
F-Web/                          # Web应用目录
├── app.py                      # Flask后端应用
├── start.bat                   # Windows启动脚本
├── test_import.py              # 导入测试脚本
├── requirements.txt            # Python依赖
├── README.md                   # 说明文档
├── templates/                  # HTML模板
│   ├── index.html             # 首页（项目介绍）
│   └── data.html              # 数据处理页面
├── static/                     # 静态资源
│   ├── home.css               # 首页样式
│   ├── home.js                # 首页脚本
│   ├── style.css              # 数据处理页面样式
│   └── app.js                 # 数据处理页面脚本
└── data/                      # 数据保存目录

A-DataBase/                     # 数据处理模块（被引用）
└── indicator_tools.py          # 技术指标计算工具
```

## ✨ 功能特性

### 首页功能
- 🎨 **现代化UI**: 蓝紫色渐变高智风格设计
- 📱 **响应式布局**: 适配各种设备屏幕
- 🎯 **项目展示**: 完整介绍项目功能和技术架构
- 👥 **团队介绍**: 展示研究团队和项目背景
- 🔗 **快速导航**: 一键跳转到数据处理功能

### 数据处理功能
- 🔍 **智能搜索**: 支持按股票代码、名称、行业、地区搜索
- 📊 **多股票选择**: 可同时选择多只股票进行批量处理
- 📈 **技术指标计算**: 自动计算MTM、MA、EMA、ATR、RSI、MACD等7大类技术指标
- 💾 **数据保存**: 处理后的数据自动保存至本地CSV文件
- 🎛️ **参数自定义**: 灵活设置日期范围和计算周期

## 🚀 快速开始

### 方法一：使用启动脚本（推荐）

双击运行 `start.bat`，脚本会自动：
1. ✅ 检查Python环境
2. ✅ 安装缺少的依赖包
3. ✅ 检查配置文件
4. ✅ 启动Flask服务器

### 方法二：手动启动

**1. 安装依赖**
```bash
cd F-Web
pip install -r requirements.txt
```

**2. 配置环境变量**

在项目根目录（`Machine_Learning_ETF/`）创建 `.env` 文件：
```env
TUSHARE_TOKEN=你的Tushare_API_Token
start_date=20230101
end_date=20241231
```

**3. 运行应用**
```bash
python app.py
```

**4. 访问应用**

打开浏览器访问：
- **首页**: http://127.0.0.1:5000
- **数据处理**: http://127.0.0.1:5000/data

## 🎯 页面导航

### 首页 (`/`)
- 项目介绍和核心功能展示
- 技术架构说明
- 团队信息
- 点击"开始使用"或"立即体验"按钮跳转到数据处理页面

### 数据处理页面 (`/data`)
- 股票搜索和批量选择
- 技术指标参数设置
- 数据处理和结果下载
- 点击左上角"返回首页"按钮返回首页

## 📊 技术指标说明

| 指标类型 | 指标名称 | 说明 |
|---------|---------|------|
| 动量指标 | MTM(5/10/20) | 当日收盘价与n日前收盘价的差值 |
| 移动平均 | MA(5/10/20) | 简单移动平均线 |
| 指数平均 | EMA(5/10/20) | 指数加权移动平均线 |
| 波动指标 | ATR | 平均真实波幅，可自定义周期 |
| 强弱指标 | RSI | 相对强弱指数，可自定义周期 |
| MACD系统 | DIF/DEA/MACD | 趋势跟踪指标组合 |
| 成交量 | 变动率 | 成交量相对变化率 |

## 模块引用说明

本应用引用了 `A-DataBase/indicator_tools.py` 中的技术指标计算函数。

**导入原理：**
```python
# 在app.py中
current_dir = os.path.dirname(os.path.abspath(__file__))  # F-Web目录
parent_dir = os.path.dirname(current_dir)                 # Machine_Learning_ETF目录
database_dir = os.path.join(parent_dir, 'A-DataBase')    # A-DataBase目录

# 添加到Python路径
sys.path.insert(0, database_dir)

# 导入模块
from indicator_tools import calculate_mtm_indicators, ...
```

**测试导入：**
```bash
python test_import.py
```

## 技术指标说明

### 动量指标 (MTM)
- MTM(5), MTM(10), MTM(20)
- 计算当日收盘价与n日前收盘价的差值

### 移动平均线 (MA)
- MA(5), MA(10), MA(20)
- 简单移动平均

### 指数移动平均线 (EMA)
- EMA(5), EMA(10), EMA(20)
- 加权移动平均

### 真实波幅 (ATR)
- 衡量市场波动性
- 可自定义计算周期（默认14日）

### 相对强弱指数 (RSI)
- 衡量超买超卖情况
- 可自定义计算周期（默认14日）

### MACD指标
- 包含DIF、DEA、MACD柱
- 趋势跟踪指标

### 成交量变动率
- 衡量成交量变化情况

## 数据保存

处理后的数据保存在 `data/` 目录下，每只股票对应一个CSV文件。
如果选择了多只股票，还会生成一个组合数据文件 `portfolio_total.csv`。

## 注意事项

1. 需要有效的Tushare API Token
2. 确保网络连接正常
3. 建议选择合理的日期范围（过长可能影响性能）
4. 数据保存路径：`F-Web/data/`

## 技术栈

- **后端**: Flask, Python
- **数据处理**: Pandas, NumPy, Tushare
- **前端**: HTML5, CSS3, JavaScript (原生)
- **UI设计**: 蓝紫色渐变主题，现代扁平化设计
