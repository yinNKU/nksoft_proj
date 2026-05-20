import scanpy as sc
import numpy as np


def load_and_preprocess(h5ad_path="liver.h5ad", n_pcs=50):
    """
    读取 liver .h5ad 文件，返回 (N, n_pcs) 的 float32 归一化向量和 AnnData 对象。

    数据说明：
      - obs 中含 cell_type（细胞类型）、disease（疾病状态）、AgeGroup（年龄分组）
      - obsm['X_pca'] 已有 PCA 降维结果，直接用；没有则自动跑预处理流程
    """
    adata = sc.read_h5ad(h5ad_path)

    if 'X_pca' not in adata.obsm:
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
        sc.pp.highly_variable_genes(adata, n_top_genes=2000)
        adata = adata[:, adata.var.highly_variable]
        sc.pp.scale(adata)
        sc.tl.pca(adata, n_comps=n_pcs)

    vectors = adata.obsm['X_pca'][:, :n_pcs].astype(np.float32)

    # L2 归一化，使内积等价于余弦相似度
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vectors = vectors / norms

    return vectors, adata


def get_metadata(adata, cell_idx):
    """获取单个细胞的元信息字典"""
    info = {'cell_id': str(adata.obs_names[cell_idx])}
    for col in adata.obs.columns:
        val = adata.obs.iloc[cell_idx][col]
        if hasattr(val, 'item'):
            val = val.item()
        info[col] = str(val)
    return info


def get_available_metadata(adata):
    """返回 obs 中所有可用的元数据列名"""
    return list(adata.obs.columns)


def get_dataset_summary(adata):
    """返回数据集概况：细胞数、基因数、元数据列、PCA 维度"""
    n_pcs = adata.obsm['X_pca'].shape[1] if 'X_pca' in adata.obsm else 0
    return {
        'n_cells': adata.n_obs,
        'n_genes': adata.n_vars,
        'n_pcs': n_pcs,
        'metadata_columns': list(adata.obs.columns),
    }
