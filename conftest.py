# -*- coding: utf-8 -*-
"""Root pytest configuration.

Ensures the project root is on sys.path so that `receivables_recovery`
resolves to the inner Python module (containing tasks.py, etc.).
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
