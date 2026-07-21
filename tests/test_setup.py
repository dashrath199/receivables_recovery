# -*- coding: utf-8 -*-
"""Shared test setup — must be imported BEFORE any source modules.

Usage in test files:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_setup import *  # noqa: F403, F401
    from test_helpers import *  # noqa: F403, F401
    from receivables_recovery.tasks import ...

This module:
1. Adds the project root to sys.path for correct package resolution
2. Mocks the `frappe` module via sys.modules injection (required for
   standalone testing without a Frappe bench)
3. Mocks `requests` (imported by messaging.py at module level)

To run these tests on a real Frappe bench instead:
    bench run-tests --module receivables_recovery.tests
"""
from __future__ import unicode_literals
import sys
from unittest.mock import MagicMock
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. sys.path — ensure project root is on the path so that
#    `receivables_recovery` resolves to the Python module
#    (the directory containing tasks.py, messaging.py, etc.)
# ---------------------------------------------------------------------------
# Frappe app root = tests/ -> repo root (2 levels up)
_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))


# ---------------------------------------------------------------------------
# 2. Mock `frappe` — the source modules import frappe at the top level,
#    so we must inject a mock into sys.modules BEFORE any of them load.
# ---------------------------------------------------------------------------

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


def _build_db_mock():
    d = MagicMock()
    d.exists = MagicMock(return_value=False)
    
    # get_value should return MockFrappeDict when as_dict=True is passed
    def _get_value_side_effect(*args, **kwargs):
        return MockFrappeDict()
    d.get_value = MagicMock(side_effect=_get_value_side_effect)
    
    d.set_value = MagicMock()
    d.sql = MagicMock()
    d.commit = MagicMock()
    d.get_single_value = MagicMock(return_value="Test Company")
    # get_all should return MockFrappeDict list for attribute access
    def _get_all_side_effect(*args, **kwargs):
        return [MockFrappeDict()]
    d.get_all = MagicMock(side_effect=_get_all_side_effect)

    d.count = MagicMock()
    return d


def _build_model_mock():
    m = MagicMock()
    m.document = MagicMock()
    m.document.Document = MagicMock
    return m


# Helper: raise an exception with a given message (used by frappe.throw mock)
def _raise_exception(msg):
    raise Exception(msg)


# Helper: dict that also supports attribute access (mimics frappe._dict)
class MockFrappeDict(dict):
    """A dict that supports both dict['key'] and obj.key access.

    Mimics frappe._dict which is used throughout the ERPNext codebase.
    """
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{key}'")
    def __setattr__(self, key, value):
        self[key] = value
    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{key}'")
    def __repr__(self):
        return f"MockFrappeDict({dict.__repr__(self)})"


# Build all mocks
_utils_mock = _build_utils_mock()
_db_mock = _build_db_mock()
_model_mock = _build_model_mock()

# Core frappe mock — MUST have __path__ = [] so Python treats it as a package
# This is required for `from frappe.utils import ...` to work.
_frappe_mock = MagicMock()
_frappe_mock.__version__ = "15.0.0"
_frappe_mock.__name__ = "frappe"
_frappe_mock.__path__ = []  # Mark as a package!

# Wire up sub-modules as attributes
_frappe_mock.utils = _utils_mock
_frappe_mock.utils.data = _utils_mock
_frappe_mock.db = _db_mock
_frappe_mock.model = _model_mock
_frappe_mock.model.document = _model_mock.document

# Wire up other attributes
# frappe.conf is a dict-like object supporting both conf.get('key') and conf.key
# Pre-populate with expected site config keys so patch.multiple works
# (patch.multiple uses hasattr which relies on __getattr__ not raising)
_frappe_mock.conf = MockFrappeDict({
    "gupshup_api_key": None,
    "gupshup_source_number": None,
    "gupshup_app_name": None,
    "msg91_auth_key": None,
    "msg91_sender_id": None,
    "whatsapp_provider": None,
    "sms_provider": None,
})

_frappe_mock.session = MagicMock()
_frappe_mock.session.user = "test@example.com"
_frappe_mock.request = MagicMock()
_frappe_mock.response = {}
_frappe_mock.get_doc = MagicMock()

# Make frappe.get_all return MockFrappeDict objects for attribute access
_frappe_mock.get_all = MagicMock()

_frappe_mock.get_roles = MagicMock()
_frappe_mock.get_attr = MagicMock()
_frappe_mock.get_meta = MagicMock()
_frappe_mock.log_error = MagicMock()
_frappe_mock.msgprint = MagicMock()

# frappe.throw should raise the actual message it receives
_frappe_mock.throw = MagicMock(side_effect=lambda *args, **kwargs: (
    _raise_exception(args[0] if args else kwargs.get('msg', 'Frappe error'))
))
_frappe_mock.ValidationError = Exception
_frappe_mock.generate_hash = MagicMock(return_value="testhash1234567890")
_frappe_mock.tests = MagicMock()
_frappe_mock.tests.utils = MagicMock()
_frappe_mock.tests.utils.FrappeTestCase = object
_frappe_mock._ = lambda x: x

# Make @frappe.whitelist() a no-op decorator
_frappe_mock.whitelist = lambda fn=None, **kwargs: fn if fn else (lambda f: f)

# ---------------------------------------------------------------------------
# 3. Mock `requests` — messaging.py does `import requests` at module level
# ---------------------------------------------------------------------------
_requests_mock = MagicMock()
_requests_mock.exceptions = MagicMock()
_requests_mock.exceptions.HTTPError = Exception
_requests_mock.exceptions.RequestException = Exception

# ---------------------------------------------------------------------------
# 4. Inject ALL modules into sys.modules unconditionally
# ---------------------------------------------------------------------------
_INJECTIONS = [
    ("frappe", _frappe_mock),
    ("frappe.utils", _utils_mock),
    ("frappe.utils.data", _utils_mock),
    ("frappe.db", _db_mock),
    ("frappe.model", _model_mock),
    ("frappe.model.document", _model_mock.document),
    ("frappe.session", _frappe_mock.session),
    ("frappe.request", _frappe_mock.request),
    ("frappe.response", _frappe_mock.response),
    ("frappe.conf", _frappe_mock.conf),
    ("frappe.tests", _frappe_mock.tests),
    ("frappe.tests.utils", _frappe_mock.tests.utils),
    ("requests", _requests_mock),
    ("requests.exceptions", _requests_mock.exceptions),
]

for _path, _mock in _INJECTIONS:
    sys.modules[_path] = _mock
