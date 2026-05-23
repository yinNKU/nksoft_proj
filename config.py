"""Project configuration.

后续开发时，尽量把路径、维度、默认索引类型等参数放到这里，
不要散落在 app.py 或各个业务模块中。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_INDEX_TYPE = "hnsw"
HNSW_M = 32
HNSW_EF_SEARCH = 64
IVF_NLIST = 100
IVF_NPROBE = 10
INDEX_DIR = BASE_DIR / "indexes"
INDEX_METADATA_SUFFIX = ".json"
INDEX_FILE_SUFFIX = ".faiss"


def _default_data_path() -> Path:
    # 优先尊重环境变量；否则自动选择 data/ 下已有的 .h5ad，便于更换真实数据集。
    env_path = os.getenv("SC_DATA_PATH")
    if env_path:
        return Path(env_path)

    sample_path = DATA_DIR / "sample.h5ad"
    if sample_path.exists():
        return sample_path

    h5ad_files = sorted(DATA_DIR.glob("*.h5ad"))
    if h5ad_files:
        return h5ad_files[0]

    return sample_path


@dataclass(frozen=True)
class Settings:
    """全局配置。

    TODO:
    - 后续可以改为读取 YAML / TOML 配置文件。
    - 后续可以区分 dev / test / prod 配置。
    """

    data_path: Path = _default_data_path()
    index_dir: Path = Path(os.getenv("SC_INDEX_DIR", INDEX_DIR))
    n_pcs: int = int(os.getenv("SC_N_PCS", "50"))
    default_index_type: str = os.getenv("SC_INDEX_TYPE", DEFAULT_INDEX_TYPE)
    default_top_k: int = int(os.getenv("SC_TOP_K", "10"))
    max_top_k: int = int(os.getenv("SC_MAX_TOP_K", "100"))
    index_file_suffix: str = INDEX_FILE_SUFFIX
    index_metadata_suffix: str = INDEX_METADATA_SUFFIX
    hnsw_m: int = int(os.getenv("SC_HNSW_M", str(HNSW_M)))
    hnsw_ef_search: int = int(os.getenv("SC_HNSW_EF_SEARCH", str(HNSW_EF_SEARCH)))
    ivf_nlist: int = int(os.getenv("SC_IVF_NLIST", str(IVF_NLIST)))
    ivf_nprobe: int = int(os.getenv("SC_IVF_NPROBE", str(IVF_NPROBE)))

    def ann_params(self) -> dict[str, int]:
        # 统一向 ANNEngine 传参，避免索引参数散落在服务层和脚本里。
        return {
            "hnsw_m": self.hnsw_m,
            "hnsw_ef_search": self.hnsw_ef_search,
            "ivf_nlist": self.ivf_nlist,
            "ivf_nprobe": self.ivf_nprobe,
        }

    def index_path(self, index_type: str) -> Path:
        # 索引文件名包含数据集 stem 和索引类型，避免多个数据集/索引互相覆盖。
        return self.index_dir / f"{Path(self.data_path).stem}_{index_type}{self.index_file_suffix}"

    def index_metadata_path(self, index_type: str) -> Path:
        return self.index_dir / f"{Path(self.data_path).stem}_{index_type}{self.index_metadata_suffix}"
