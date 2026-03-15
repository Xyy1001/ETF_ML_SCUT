import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import SymLogNorm


def plot_training_curves(train_losses: np.ndarray, out_path: str) -> None:
    """绘制训练损失曲线并保存为图片。"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.figure(figsize=(6, 4))
    plt.plot(train_losses, label='Train Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.title('Training Loss Convergence')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_corr_matrices(true_corr: np.ndarray, pred_corr: np.ndarray, out_dir: str, step: int = 0) -> None:
    """
    对比绘制真实/预测相关系数矩阵热力图。
    颜色范围固定在 [-1, 1]。
    """
    os.makedirs(out_dir, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # 相关系数矩阵的颜色范围固定为 [-1, 1]
    vmin, vmax = -1, 1
    cmap = 'RdBu_r'  # 红色代表正相关，蓝色代表负相关

    im0 = axes[0].imshow(true_corr, cmap=cmap, vmin=vmin, vmax=vmax)
    axes[0].set_title('True Correlation Matrix')
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    im1 = axes[1].imshow(pred_corr, cmap=cmap, vmin=vmin, vmax=vmax)
    axes[1].set_title('Predicted Correlation Matrix')
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f'corr_comparison_step{step}.png'), dpi=150)
    plt.close(fig)


