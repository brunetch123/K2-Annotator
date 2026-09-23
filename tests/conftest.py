import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
K2_SCRIPTS = os.path.join(REPO, 'scripts')
SYNTH_DIR = os.path.join(HERE, 'synth')
DATA_DIR = os.path.join(SYNTH_DIR, 'data')

for p in (K2_SCRIPTS, SYNTH_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope='session')
def k2_scripts():
    return K2_SCRIPTS


@pytest.fixture(scope='session')
def dataset():
    """Generate the synthetic dataset once per session; return (dir, truth)."""
    import make_dataset
    truth = make_dataset.write_dataset(DATA_DIR)
    return DATA_DIR, truth
