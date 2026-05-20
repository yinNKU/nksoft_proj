"""Project configuration.

后续开发时，尽量把路径、维度、默认索引类型等参数放到这里，
不要散落在 app.py 或各个业务模块中。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    """全局配置。

    TODO:
    - 后续可以改为读取 YAML / TOML 配置文件。
    - 后续可以区分 dev / test / prod 配置。
    """

    data_path: Path = Path(os.getenv("SC_DATA_PATH", BASE_DIR / "data" / "sample.h5ad"))
    index_dir: Path = Path(os.getenv("SC_INDEX_DIR", BASE_DIR / "indexes"))
    n_pcs: int = int(os.getenv("SC_N_PCS", "50"))
    default_index_type: str = os.getenv("SC_INDEX_TYPE", "hnsw")
    default_top_k: int = int(os.getenv("SC_TOP_K", "10"))
    max_top_k: int = int(os.getenv("SC_MAX_TOP_K", "100"))
