import os
import numpy as np
import torch
import yaml

from transformer_encoder import NodeTransformerEncoder
from gnn_model import GNNModel, frobenius_mse_loss
from datasets import get_dataloaders
from plot_utils import plot_training_curves, plot_cov_matrices


def _read_yaml_config(path: str):
    """读取 YAML 配置。"""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def evaluate(config_path: str = 'configs/variables.yaml'):
    """评估入口：加载模型与数据 → 计算测试 MSE → 保存可视化与报告。"""
    cfg = _read_yaml_config(config_path)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # 加载数据
    data_dir = "data"
    
    # 加载训练集数据
    train_node_feats = np.load(os.path.join(data_dir, "train_node_features_norm.npy"))
    train_edge_feat = np.load(os.path.join(data_dir, "train_edge_features.npy"))
    train_targets = np.load(os.path.join(data_dir, "train_targets.npy"))
    
    # 加载测试集数据
    test_node_feats = np.load(os.path.join(data_dir, "test_node_features_norm.npy"))
    test_edge_feat = np.load(os.path.join(data_dir, "test_edge_features.npy"))
    test_targets = np.load(os.path.join(data_dir, "test_targets.npy"))
    
    train_loader, test_loader = get_dataloaders(
        train_node_feats=train_node_feats,
        train_edge_feat=train_edge_feat,
        train_targets=train_targets,
        test_node_feats=test_node_feats,
        test_edge_feat=test_edge_feat,
        test_targets=test_targets,
        batch_size=int(cfg['gnn_training']['batch_size']),
    )

    # 加载训练好的模型
    model_path = cfg['gnn_training']['save_model_path']
    checkpoint = torch.load(model_path, map_location=device)
    encoder = NodeTransformerEncoder(
        d_model=int(cfg['transformer']['d_model']),
        nhead=int(cfg['transformer']['nhead']),
        num_layers=int(cfg['transformer']['num_layers']),
        dropout=float(cfg['transformer']['dropout']),
    ).to(device).double()
    gnn = GNNModel(
        node_in_dim=int(cfg['transformer']['d_model']),
        hidden_dim=int(cfg['gnn_training']['hidden_dim']),
        num_layers=int(cfg['gnn_training']['num_layers']),
        dropout=float(cfg['gnn_training']['dropout']),
    ).to(device).double()
    encoder.load_state_dict(checkpoint['encoder_state_dict'])
    gnn.load_state_dict(checkpoint['gnn_state_dict'])
    encoder.eval(); gnn.eval()

    # 在测试集上评估
    all_losses = []
    all_predicted_matrices = []  # 存储所有预测的协方差矩阵
    all_true_matrices = []       # 存储所有真实的协方差矩阵
    example_true = None
    example_pred = None
    with torch.no_grad():
        for idx, (nf, ef, tg) in enumerate(test_loader):
            nf = nf.to(device)
            ef = ef.to(device)
            tg = tg.to(device)
            enc = encoder(nf)
            pred = gnn(enc, ef)
            loss = frobenius_mse_loss(pred, tg)
            all_losses.append(loss.item())
            
            # 收集所有预测和真实的协方差矩阵
            batch_pred = pred.detach().cpu().numpy()
            batch_true = tg.detach().cpu().numpy()
            all_predicted_matrices.append(batch_pred)
            all_true_matrices.append(batch_true)
            
            if example_true is None:
                example_true = tg[0].detach().cpu().numpy()
                example_pred = pred[0].detach().cpu().numpy()

    mse = float(np.mean(all_losses))
    os.makedirs(cfg['outputs']['results_dir'], exist_ok=True)
    
    # 保存所有预测的协方差矩阵
    all_predicted_matrices = np.concatenate(all_predicted_matrices, axis=0)
    all_true_matrices = np.concatenate(all_true_matrices, axis=0)
    
    predicted_matrices_path = os.path.join(cfg['outputs']['results_dir'], 'predicted_covariance_matrices.npy')
    true_matrices_path = os.path.join(cfg['outputs']['results_dir'], 'true_covariance_matrices.npy')
    
    np.save(predicted_matrices_path, all_predicted_matrices)
    np.save(true_matrices_path, all_true_matrices)
    
    print(f"保存了 {all_predicted_matrices.shape[0]} 个预测协方差矩阵到: {predicted_matrices_path}")
    print(f"保存了 {all_true_matrices.shape[0]} 个真实协方差矩阵到: {true_matrices_path}")
    print(f"矩阵形状: {all_predicted_matrices.shape}")
    
    with open(cfg['outputs']['mse_score'], 'w', encoding='utf-8') as f:
        f.write(f"MSE (avg Frobenius) on test set: {mse:.8f}\n")

    # plots
    if os.path.exists(os.path.join('results', 'train_losses.npy')):
        train_losses = np.load(os.path.join('results', 'train_losses.npy'))
        plot_training_curves(train_losses, os.path.join(cfg['outputs']['results_dir'], 'training_curves.png'))

    if example_true is not None and example_pred is not None:
        plot_cov_matrices(example_true, example_pred, cfg['outputs']['results_dir'], step=0)



    with open(cfg['outputs']['evaluation_report'], 'w', encoding='utf-8') as f:
        f.write(f"Test MSE: {mse:.8f}\n")
        f.write(f"Total predicted matrices saved: {all_predicted_matrices.shape[0]}\n")
        f.write(f"Matrix shape: {all_predicted_matrices.shape[1:]}\n")
        f.write(f"Predicted matrices saved to: {predicted_matrices_path}\n")
        f.write(f"True matrices saved to: {true_matrices_path}\n")
        f.write("Plots saved to results directory.\n")

    print("Evaluation complete.")


if __name__ == '__main__':
    evaluate()


