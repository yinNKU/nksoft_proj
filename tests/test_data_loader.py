from __future__ import annotations

import numpy as np
import pandas as pd

from src.data_loader import (
    get_available_metadata,
    get_dataset_summary,
    get_metadata,
    l2_normalize,
)


class DummyAnnData:
    def __init__(self) -> None:
        self.obs = pd.DataFrame(
            {
                "cell_type": ["hepatocyte", "immune"],
                "disease": ["normal", "fibrosis"],
            },
            index=["cell_a", "cell_b"],
        )
        self.obs_names = self.obs.index
        self.obsm = {"X_pca": np.ones((2, 3), dtype=np.float32)}
        self.n_obs = 2
        self.n_vars = 5


def test_l2_normalize_handles_zero_vectors():
    vectors = np.array([[3.0, 4.0], [0.0, 0.0]], dtype=np.float32)

    normalized = l2_normalize(vectors)

    assert np.allclose(normalized[0], [0.6, 0.8])
    assert np.allclose(normalized[1], [0.0, 0.0])


def test_metadata_helpers_return_json_ready_values():
    adata = DummyAnnData()

    assert get_available_metadata(adata) == ["cell_type", "disease"]
    assert get_metadata(adata, 1) == {
        "cell_id": "cell_b",
        "cell_type": "immune",
        "disease": "fibrosis",
    }
    assert get_dataset_summary(adata) == {
        "n_cells": 2,
        "n_genes": 5,
        "n_pcs": 3,
        "metadata_columns": ["cell_type", "disease"],
    }
