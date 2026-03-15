# LSTM+Transformer 运行指南

本目录包含一个用于股票多变量时间序列预测的 LSTM+Transformer 融合模型实现，覆盖训练、测试与预测脚本。

## 目录说明

- TrainingModel.py: 训练模型并保存权重（按 CSV 文件逐只股票训练）。
- TestingModel.py: 加载模型，对测试集预测并可视化评估。
- predict_with_model.py: 使用 tushare 拉取历史数据并预测未来 N 天。
- predict_range.py: 用历史区间作为输入，预测指定未来交易日区间。

## 环境依赖

建议 Python 3.8+。

基础依赖（训练/测试必需）:

- torch
- pandas
- numpy
- scikit-learn
- matplotlib

预测脚本额外依赖:

- tushare

示例安装命令:

```
pip install torch pandas numpy scikit-learn matplotlib tushare
```

## 数据准备

TrainingModel.py 以“一个 CSV 文件 = 一只股票”为单位训练。每个 CSV 需要至少包含:

- close: 目标变量（收盘价）
- 其他任意数值列作为特征（例如 open/high/low/vol/amount 等）

注意:

- 训练数据会自动进行缺失值填充与数值清理。
- 特征列的选择逻辑是“除 close 之外的所有数值列”。如果不希望某列参与训练，请在 CSV 中将其改为非数值列或提前删除。

## 训练模型

TrainingModel.py 内部有一个默认数据目录变量 `folder_path`，需要根据你的实际数据位置修改。

1) 打开 TrainingModel.py，修改 `folder_path` 指向你的 CSV 目录。
2) 确保模型输出目录存在（默认保存到 `ETF/model/`）:

```
New-Item -ItemType Directory -Force ETF\model
```

3) 运行训练:

```
python TrainingModel.py
```

训练脚本会遍历目录下所有 CSV，每个文件训练一个模型，并保存为:

```
ETF/model/{csv文件名}.pth
```

## 测试与可视化

TestingModel.py 会读取你输入的数据目录，并进行预测与可视化。

运行方式:

```
python TestingModel.py
```

注意事项:

- TestingModel.py 中的 `model_path` 需要指向具体的 `.pth` 文件。如果你使用的是训练输出 `ETF/model/{csv文件名}.pth`，请在文件中调整为对应路径。
- 预测结果与图像会保存到 `Transformer+LSTM/Advanced/prediction`（如需修改请在脚本中调整）。

## 使用模型预测未来 N 天

使用 tushare 拉取历史数据并预测未来 N 天:

```
python predict_with_model.py --ts_code 000001.SZ --start_date 20240101 --end_date 20251031 --predict_days 10
```

可选参数:

- `--model_path` 指定模型文件路径（默认 `Models/{ts_code}.pth`）
- `--input_window` 输入窗口长度（默认 100）
- `--tushare_token` tushare token（也可用环境变量 `TUSHARE_TOKEN`）

PowerShell 设置 token 示例:

```
$env:TUSHARE_TOKEN = "YOUR_TOKEN"
```

输出:

- 预测结果 CSV 会保存到本目录下的 `predictions/`。

## 按交易日区间预测

指定历史区间作为输入，并预测未来交易日区间:

```
python predict_range.py --ts_code 000001.SZ --hist_start 20240101 --hist_end 20250101 --pred_start 20250102 --pred_end 20250115
```

注意:

- 如果历史区间数据不足以覆盖 `input_window`，脚本会自动补齐并打印警告。
- 输出会打印到终端，可选择保存到 CSV。

## 常见问题

- 历史数据不足 `input_window`: 扩大历史区间或降低 `input_window`。
- 预测时报 input_size 不匹配: 训练和预测的特征列不一致，请确保 CSV 列一致。
- 模型文件不存在: 使用 `--model_path` 指向正确的 `.pth` 文件，或将模型放到脚本默认路径。
