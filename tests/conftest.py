# -*- coding: utf-8 -*-
"""Minimal test configuration — sets up sys.path only.

Frappe mocking is handled by test_setup.py (imported by each test file),
not by this conftest. Keeping mock setup in one place (test_setup.py)
avoids conflicts between two different mock implementations.
"""
from __future__ import unicode_literals
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure correct sys.path for the receivables_recovery Python module
# ---------------------------------------------------------------------------
# conftest.py is at: tests/conftest.py
# The Frappe app root is 2 levels up: tests/ -> repo root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
