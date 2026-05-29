"""Shared pytest fixtures: generate a fresh seeded dataset into a temp dir and load it."""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from app.tools.csv_loader import load_all  # noqa: E402
from generate_synthetic_data import generate  # noqa: E402

SEED = 42


@pytest.fixture(scope="session")
def gen_dir(tmp_path_factory):
    """A directory containing one seeded generation (seed=42, demo scale)."""
    d = tmp_path_factory.mktemp("synthetic_seed42")
    generate(seed=SEED, scale_name="demo", outdir=d)
    return d


@pytest.fixture(scope="session")
def tables(gen_dir):
    return load_all(gen_dir)
