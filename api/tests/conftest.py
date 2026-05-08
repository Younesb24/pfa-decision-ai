"""Pytest configuration: makes api/ importable as a top-level package root."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # .../api
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Provide non-secret defaults so module-level db config doesn't blow up at import.
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_DB", "pfa_olist_test")
