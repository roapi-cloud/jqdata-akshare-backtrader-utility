from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def pytest_sessionstart(session):
    root = Path(__file__).resolve().parents[3] / "skills"
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    np.random.seed(42)

