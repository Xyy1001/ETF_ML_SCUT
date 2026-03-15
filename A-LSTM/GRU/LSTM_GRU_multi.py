"""
模型构建 LSTM + GRU（多股票）
1. 构建 LSTM + GRU 融合模型
2. 训练模型
3. 保存训练曲线
4. 保存模型

示例:
python GRU/LSTM_GRU_multi.py --data-dir data --model-dir model_gru --plot-dir plots_gru
"""
import argparse
import os
import re

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset
import matplotlib.pyplot as plt

DEFAULT_FOLDER_PATH = "/root/ETF/data/raw_data"


def fill_missing_values(df):
    print("开始缺失值填充...")
    missing_info = df.isnull().sum()
    print(f"缺失值统计:\n{missing_info[missing_info > 0]}")

    for col in df.columns:
        if df[col].isnull().any():
            df[col] = df[col].fillna(method="ffill")
            df[col] = df[col].fillna(method="bfill")

    remaining_missing = df.isnull().sum().sum()
    print(f"填充后剩余缺失值数量: {remaining_missing}")
    return df


def load_stock_data_csv(folder_path):
    if not folder_path:
        print("未提供数据文件夹路径")
        return None
    if not os.path.exists(folder_path):
        print(f"文件夹不存在，请检查路径: {folder_path}")
        return None
    if not os.path.isdir(folder_path):
        print(f"路径不是文件夹，请检查路径: {folder_path}")
        return None

    files = os.listdir(folder_path)
    dataframes = []
    for file in files:
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(folder_path, file))
            df = fill_missing_values(df)
            df.name = re.sub(r"\.csv$", "", file)
            dataframes.append(df)

    if not dataframes:
        print("未找到任何CSV文件")
        return None

    print(f"读取到 {len(dataframes)} 个数据文件")
    print(f"数据文件列表: {files}")
    return dataframes


def preprocess_data(data):
    missing_info = {}
    total_missing = 0

    print("\n=== 缺失值检查和处理 ===")
    for i, col_name in enumerate(data.columns):
        col_data = data.iloc[:, i]
        missing_count = col_data.isnull().sum()
        if pd.api.types.is_numeric_dtype(col_data):
            missing_count += np.isinf(col_data).sum()

        if missing_count > 0:
            print(f"列 {i+1} ({col_name}): 发现 {missing_count} 个缺失值")
            missing_info[f"列{i+1}_{col_name}"] = missing_count
            total_missing += missing_count

            if i == 0:
                data.iloc[:, i] = data.iloc[:, i].fillna(method="ffill")
                data.iloc[:, i] = data.iloc[:, i].fillna(method="bfill")
            else:
                data.iloc[:, i] = data.iloc[:, i].replace([np.inf, -np.inf], np.nan)
                data.iloc[:, i] = data.iloc[:, i].fillna(method="ffill")
                data.iloc[:, i] = data.iloc[:, i].fillna(method="bfill")
                data.iloc[:, i] = data.iloc[:, i].fillna(0)
        else:
            print(f"列 {i+1} ({col_name}): 无缺失值")

    print("\n缺失值处理总结:")
    print(f"总共处理了 {total_missing} 个缺失值")
    if missing_info:
        print("各列缺失值详情:")
        for col_info, count in missing_info.items():
            print(f"  {col_info}: {count} 个")
    else:
        print("数据完整，无缺失值")

    final_missing = data.isnull().sum().sum()
    if final_missing > 0:
        print(f"警告: 处理后仍有 {final_missing} 个缺失值")
    else:
        print("✓ 所有缺失值已成功处理")
    return data


class StockTimeSeriesDataset(Dataset):
    def __init__(self, data, input_window=100, output_window=10, target_col="close"):
        if target_col in data.columns:
            self.target = data[target_col].values
            self.features = data.drop(columns=[target_col]).select_dtypes(include=[np.number]).values
        else:
            print(f"警告: 未找到列'{target_col}',使用第一列作为目标变量")
            self.target = data.iloc[:, 0].values
            self.features = data.iloc[:, 1:].select_dtypes(include=[np.number]).values

        self.input_window = input_window
        self.output_window = output_window
        self.total_window = self.input_window + self.output_window
        self.n_samples = len(self.target) - input_window - output_window + 1

        print(f"数据集样本数量: {self.n_samples}")
        print(f"目标变量形状: {self.target.shape}")
        print(f"特征变量形状: {self.features.shape}")
        print(f"每个样本包含天数: {self.total_window} (input={self.input_window}, output={self.output_window})")

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        input_target = self.target[idx:idx + self.input_window]
        input_features = self.features[idx:idx + self.input_window]

        target_scaler = StandardScaler()
        input_target_arr = np.asarray(input_target)
        input_target_arr = np.nan_to_num(input_target_arr, nan=0.0, posinf=0.0, neginf=0.0)
        if np.std(input_target_arr) <= 1e-8:
            input_target_scaled = input_target_arr - np.mean(input_target_arr)
        else:
            input_target_scaled = target_scaler.fit_transform(input_target_arr.reshape(-1, 1)).flatten()

        input_features_arr = np.asarray(input_features)
        input_features_arr = np.nan_to_num(input_features_arr, nan=0.0, posinf=0.0, neginf=0.0)
        input_features_scaled = np.zeros_like(input_features_arr)
        for i in range(input_features_arr.shape[1]):
            feature_data = input_features_arr[:, i]
            feature_data = np.nan_to_num(feature_data, nan=0.0, posinf=0.0, neginf=0.0)
            if np.std(feature_data) <= 1e-8:
                input_features_scaled[:, i] = feature_data - np.mean(feature_data)
            else:
                feature_scaler = StandardScaler()
                input_features_scaled[:, i] = feature_scaler.fit_transform(
                    feature_data.reshape(-1, 1)
                ).flatten()

        output_target = self.target[idx + self.input_window:idx + self.input_window + self.output_window]
        output_target_arr = np.asarray(output_target)
        output_target_arr = np.nan_to_num(output_target_arr, nan=0.0, posinf=0.0, neginf=0.0)
        if np.std(input_target_arr) <= 1e-8:
            output_target_scaled = output_target_arr - np.mean(input_target_arr)
        else:
            output_target_scaled = target_scaler.transform(output_target_arr.reshape(-1, 1)).flatten()

        input_target_scaled = np.nan_to_num(input_target_scaled, nan=0.0, posinf=0.0, neginf=0.0)
        input_features_scaled = np.nan_to_num(input_features_scaled, nan=0.0, posinf=0.0, neginf=0.0)
        output_target_scaled = np.nan_to_num(output_target_scaled, nan=0.0, posinf=0.0, neginf=0.0)
        output_target_arr = np.nan_to_num(output_target_arr, nan=0.0, posinf=0.0, neginf=0.0)

        input_combined = np.column_stack([input_target_scaled, input_features_scaled])
        return (
            torch.FloatTensor(input_combined),
            torch.FloatTensor(output_target_scaled),
            torch.FloatTensor(output_target_arr),
            target_scaler,
        )


class LSTM_GRU_Model(nn.Module):
    def __init__(
        self,
        input_size=23,
        lstm_hidden_size=64,
        lstm_layers=1,
        gru_hidden_size=64,
        gru_layers=1,
        dropout=0.1,
        output_size=1,
        output_window=10,
    ):
        super().__init__()
        self.output_window = output_window
        self.lstm = nn.LSTM(
            input_size,
            lstm_hidden_size,
            lstm_layers,
            batch_first=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
        )
        self.gru = nn.GRU(
            lstm_hidden_size,
            gru_hidden_size,
            gru_layers,
            batch_first=True,
            dropout=dropout if gru_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(gru_hidden_size, output_size * output_window)

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        gru_out, _ = self.gru(lstm_out)
        last_output = gru_out[:, -1, :]
        output = self.fc(last_output)
        return output.view(x.size(0), self.output_window, -1)


def custom_collate_fn(batch):
    inputs, targets_scaled, targets_original, scalers = zip(*batch)
    inputs = torch.stack(inputs)
    targets_scaled = torch.stack(targets_scaled)
    targets_original = torch.stack(targets_original)

    inputs = torch.nan_to_num(inputs, nan=0.0, posinf=0.0, neginf=0.0)
    targets_scaled = torch.nan_to_num(targets_scaled, nan=0.0, posinf=0.0, neginf=0.0)
    targets_original = torch.nan_to_num(targets_original, nan=0.0, posinf=0.0, neginf=0.0)
    inputs = torch.clamp(inputs, -10.0, 10.0)
    targets_scaled = torch.clamp(targets_scaled, -10.0, 10.0)

    return inputs, targets_scaled, targets_original, scalers


def train_and_save_model(train_loader, num_epochs, learning_rate, model_path):
    sample_inputs, sample_targets_scaled, _, _ = next(iter(train_loader))
    inferred_input_size = sample_inputs.shape[-1]
    inferred_output_window = sample_targets_scaled.shape[-1]

    model = LSTM_GRU_Model(
        input_size=inferred_input_size,
        lstm_hidden_size=64,
        lstm_layers=1,
        gru_hidden_size=64,
        gru_layers=1,
        dropout=0.1,
        output_size=1,
        output_window=inferred_output_window,
    )

    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)

    train_losses = []
    train_accuracies = []

    model.train()
    print("开始训练...")

    for epoch in range(num_epochs):
        epoch_loss = 0
        epoch_mape = 0
        batch_count = 0
        mape_samples = 0

        for inputs, targets_scaled, targets_original, scalers in train_loader:
            optimizer.zero_grad()
            outputs = model(inputs)
            outputs = outputs.squeeze(-1)

            loss = criterion(outputs, targets_scaled)
            if not torch.isfinite(loss):
                print(f"警告：第{epoch+1}轮第{batch_count}批次loss异常: {loss.item()}")
                optimizer.zero_grad()
                continue

            loss.backward()
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
            if not torch.isfinite(grad_norm):
                print(f"警告：第{epoch+1}轮第{batch_count}批次梯度异常")
                optimizer.zero_grad()
                continue

            optimizer.step()

            batch_loss = 0
            batch_mape = 0
            valid_samples = 0
            for i in range(outputs.shape[0]):
                try:
                    pred_original = scalers[i].inverse_transform(
                        outputs[i].detach().cpu().numpy().reshape(-1, 1)
                    ).flatten()
                    target_original = targets_original[i].cpu().numpy()

                    if np.isnan(pred_original).any() or np.isnan(target_original).any():
                        continue

                    sample_mse = np.mean((pred_original - target_original) ** 2)
                    if not np.isnan(sample_mse):
                        batch_loss += sample_mse
                        valid_samples += 1

                    denom = np.maximum(np.abs(target_original), 1e-6)
                    sample_mape = np.mean(np.abs(pred_original - target_original) / denom)
                    if not np.isnan(sample_mape):
                        batch_mape += sample_mape
                except Exception as e:
                    print(f"反标准化错误: {e}")
                    continue

            if valid_samples > 0:
                batch_loss = batch_loss / valid_samples
                epoch_loss += batch_loss
                if batch_mape > 0:
                    epoch_mape += batch_mape / valid_samples
                    mape_samples += 1
            else:
                epoch_loss += loss.item()

            batch_count += 1

        avg_loss = epoch_loss / batch_count
        train_losses.append(avg_loss)

        if mape_samples > 0:
            avg_mape = epoch_mape / mape_samples
            accuracy_rate = max(0.0, 1.0 - avg_mape)
        else:
            accuracy_rate = 0.0
        train_accuracies.append(accuracy_rate)

        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{num_epochs}], Loss (反标准化后): {avg_loss:.6f}")

    print("训练完成！")
    torch.save(model.state_dict(), model_path)
    print(f"模型已保存到 {model_path}")

    return train_losses, train_accuracies


def parse_args():
    parser = argparse.ArgumentParser(description="训练 LSTM + GRU 股票预测模型（多股票）")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="CSV文件夹路径（为空则提示输入）",
    )
    parser.add_argument(
        "--input-window",
        type=int,
        default=100,
        help="输入窗口长度（历史天数）",
    )
    parser.add_argument(
        "--output-window",
        type=int,
        default=10,
        help="输出窗口长度（预测天数）",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="训练轮数",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=0.005,
        help="学习率",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="ETF/model",
        help="模型保存目录",
    )
    parser.add_argument(
        "--plot-dir",
        type=str,
        default="ETF/plots",
        help="训练曲线图保存目录",
    )
    return parser.parse_args()


def resolve_data_dir(cli_path):
    if cli_path:
        return cli_path
    user_input = input(f"请输入CSV文件夹路径 (默认: {DEFAULT_FOLDER_PATH}): ").strip()
    return user_input if user_input else DEFAULT_FOLDER_PATH


if __name__ == "__main__":
    np.random.seed(42)
    torch.manual_seed(42)

    args = parse_args()
    data_dir = resolve_data_dir(args.data_dir)

    dataframes = load_stock_data_csv(data_dir)
    if not dataframes:
        print("数据加载失败，程序结束。")
        raise SystemExit(1)

    print("数据加载完成！")
    print(f"数据集数量: {len(dataframes)}")

    for data in dataframes:
        print(f"\n=== 开始训练: {data.name} ===")
        data = preprocess_data(data)
        train_data, test_data = train_test_split(data, test_size=0.1, shuffle=False)

        train_dataset = StockTimeSeriesDataset(train_data, args.input_window, args.output_window)
        test_dataset = StockTimeSeriesDataset(test_data, args.input_window, args.output_window)
        print(f"训练集样本数: {len(train_dataset)}")
        print(f"测试集样本数: {len(test_dataset)}")

        train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True, collate_fn=custom_collate_fn)

        os.makedirs(args.model_dir, exist_ok=True)
        os.makedirs(args.plot_dir, exist_ok=True)
        model_path = os.path.join(args.model_dir, f"{data.name}.pth")
        plot_path = os.path.join(args.plot_dir, f"{data.name}.png")

        train_losses, train_accuracies = train_and_save_model(
            train_loader,
            num_epochs=args.epochs,
            learning_rate=args.lr,
            model_path=model_path,
        )

        epochs = np.arange(1, len(train_losses) + 1)
        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax1.plot(epochs, train_losses, color="tab:blue", label="Loss (MSE)")
        ax1.set_xlabel("Epoch")
        ax1.set_ylabel("Loss (MSE)", color="tab:blue")
        ax1.tick_params(axis="y", labelcolor="tab:blue")

        ax2 = ax1.twinx()
        ax2.plot(epochs, train_accuracies, color="tab:orange", label="Accuracy Rate (1 - MAPE)")
        ax2.set_ylabel("Accuracy Rate", color="tab:orange")
        ax2.tick_params(axis="y", labelcolor="tab:orange")

        plt.title(f"Training Curves - {data.name}")
        fig.tight_layout()
        plt.savefig(plot_path)
        plt.close(fig)
        print(f"训练曲线已保存到 {plot_path}")
