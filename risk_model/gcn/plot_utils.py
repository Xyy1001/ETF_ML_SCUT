import os

import matplotlib.pyplot as plt
import numpy as np


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


def plot_cov_matrices(true_cov: np.ndarray, pred_cov: np.ndarray, out_dir: str, step: int = 0) -> None:
    """对比绘制真实/预测协方差矩阵热力图。"""
    os.makedirs(out_dir, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    im0 = axes[0].imshow(true_cov, cmap='viridis')
    axes[0].set_title('True Covariance Matrix')
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    im1 = axes[1].imshow(pred_cov, cmap='viridis')
    axes[1].set_title('Predicted Covariance Matrix')
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, f'cov_comparison_step{step}.png'), dpi=150)
    plt.close(fig)


