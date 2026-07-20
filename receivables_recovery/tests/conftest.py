# -*- coding: utf-8 -*-
"""Standalone test configuration — mocks the `frappe` module via sys.modules.

This conftest is the FIRST thing pytest loads when collecting tests from this
directory. It injects a MagicMock-based `frappe` into sys.modules so that all
imports of `frappe` (and its submodules) resolve to mocks BEFORE any test file
or source module is loaded.

This is the standard pattern for testing Frappe apps without a running site.
To run these tests on a real Frappe bench instead:
    bench run-tests --module receivables_recovery.tests
"""
from __future__ import unicode_literals
import sys
from unittest.mock import MagicMock
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Ensure correct sys.path for the receivables_recovery Python module
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # tests/../../
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 2. Build the complete frappe mock tree BEFORE injecting into sys.modules
# ---------------------------------------------------------------------------

# --utils sub-module (shared by frappe.utils and frappe.utils.data)--
def _build_utils_mock():
    u = MagicMock()
    u.today = MagicMock(return_value="2026-07-20")
    u.now = MagicMock(return_value="2026-07-20 10:00:00")
    u.now_datetime = MagicMock()
    u.date_diff = MagicMock(return_value=19)
    u.add_days = MagicMock()
    u.flt = MagicMock()
    u.getdate = MagicMock()
    u.get_datetime = MagicMock()
    u.get_url = MagicMock(return_value="http://test.local")
    u.cstr = MagicMock()
    return u


# --db sub-module--
def _build_db_mock():
    d = MagicMock()
    d.exists = MagicMock(return_value=False)
    d.get_value = MagicMock()
    d.set_value = MagicMock()
    d.sql = MagicMock()
    d.commit = MagicMock()
    d.get_single_value = MagicMock(return_value="Test Company")
    d.get_all = MagicMock()
    d.count = MagicMock()
    return d


# --model sub-module--
def _build_model_mock():
    m = MagicMock()
    m.document = MagicMock()
    m.document.Document = MagicMock
    return m


# --core frappe module--
def _build_frappe_mock():
    f = MagicMock()
    f.__version__ = "15.0.0"
    f.__name__ = "frappe"
    f.__path__ = []  # Mark as a package so submodule imports work
    f.conf = {}
    f.session = MagicMock()
    f.session.user = "test@example.com"
    f.request = MagicMock()
    f.response = {}
    f.get_doc = MagicMock()
    f.get_all = MagicMock()
    f.get_roles = MagicMock()
    f.get_attr = MagicMock()
    f.get_meta = MagicMock()
    f.log_error = MagicMock()
    f.msgprint = MagicMock()
    f.throw = MagicMock(side_effect=Exception("Frappe threw an error"))
    f.ValidationError = Exception
    f.generate_hash = MagicMock(return_value="testhash1234567890")
    f.tests = MagicMock()
    f.tests.utils = MagicMock()
    f.tests.utils.FrappeTestCase = object
    f._ = lambda x: x
    # Make @frappe.whitelist() a no-op decorator
    f.whitelist = MagicMock()
    f.whitelist.return_value = lambda fn: fn
    f.whitelist.allow_guest = MagicMock()
    f.whitelist.allow_guest.return_value = lambda fn: fn
    return f


# ---------------------------------------------------------------------------
# 3. Inject into sys.modules — build sub-modules as attributes first,
#    then insert them all without overwriting each other.
# ---------------------------------------------------------------------------

utils_mock = _build_utils_mock()
db_mock = _build_db_mock()
model_mock = _build_model_mock()
frappe_mock = _build_frappe_mock()

# Wire up sub-module attributes on the parent mock
frappe_mock.utils = utils_mock
frappe_mock.utils.data = utils_mock
frappe_mock.db = db_mock
frappe_mock.model = model_mock
frappe_mock.model.document = model_mock.document

# Now inject all modules in order — use direct assignment rather than
# a helper function to avoid accidental overwrites
injections = [
    ("frappe", frappe_mock),
    ("frappe.utils", utils_mock),
    ("frappe.utils.data", utils_mock),
    ("frappe.db", db_mock),
    ("frappe.model", model_mock),
    ("frappe.model.document", model_mock.document),
    ("frappe.session", frappe_mock.session),
    ("frappe.request", frappe_mock.request),
    ("frappe.response", frappe_mock.response),
    ("frappe.conf", frappe_mock.conf),
    ("frappe.tests", frappe_mock.tests),
    ("frappe.tests.utils", frappe_mock.tests.utils),
]

# Also mock requests (imported at module level by messaging.py)
requests_mock = MagicMock()
requests_mock.exceptions = MagicMock()
requests_mock.exceptions.HTTPError = Exception
requests_mock.exceptions.RequestException = Exception

sys.modules["requests"] = requests_mock
sys.modules["requests.exceptions"] = requests_mock.exceptions

# Inject frappe modules
for module_path, mock_obj in injections:
    if module_path not in sys.modules:
        sys.modules[module_path] = mock_obj
