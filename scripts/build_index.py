"""Command-line helper for building an ANN index.

Usage:
    python scripts/build_index.py

TODO:
- 接收命令行参数：
  - --data
  - --index-type
  - --output
  - --n-pcs
- 保存 index metadata。
"""

from __future__ import annotations

from config import Settings
from src.ann_engine import ANNEngine
from src.data_loader import prepare_dataset


def main() -> None:
    settings = Settings()
    vectors, _, _ = prepare_dataset(settings.data_path, n_pcs=settings.n_pcs)

    engine = ANNEngine()
    engine.build_index(vectors, index_type=settings.default_index_type)

    output = settings.index_dir / f"{settings.default_index_type}.faiss"
    engine.save_index(output)
    print(f"Index saved to: {output}")


if __name__ == "__main__":
    main()
