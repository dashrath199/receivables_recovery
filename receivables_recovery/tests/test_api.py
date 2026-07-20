# -*- coding: utf-8 -*-
"""Unit tests for receivables_recovery.api module.

Tests cover:
- gupshup_webhook() — delivery status callbacks from Gupshup
- msg91_webhook() — delivery reports from MSG91
- get_permission_query_conditions_for_dunning() — role-based access
- has_dunning_permission() — document-level permission checks
- validate_dunning() — document validation before save
"""
from __future__ import unicode_literals
import sys
from pathlib import Path

# Must import test_setup BEFORE any receivables_recovery source modules
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from test_setup import *  # noqa: F403, F401 — mocks frappe via sys.modules
from test_helpers import *  # noqa: F403, F401

import unittest
from unittest.mock import patch, MagicMock


class TestGupshupWebhook(unittest.TestCase):
    """Tests for gupshup_webhook()."""

    def setUp(self):
        # Patch frappe.request and frappe.response before each test
        self.request_patcher = patch(
            "receivables_recovery.api.frappe.request"
        )
        self.mock_request = self.request_patcher.start()

        self.response_patcher = patch(
            "receivables_recovery.api.frappe.response", new_callable=dict
        )
        self.mock_response = self.response_patcher.start()

    def tearDown(self):
        self.request_patcher.stop()
        self.response_patcher.stop()

    def test_invalid_json_returns_400(self):
        from receivables_recovery.api import gupshup_webhook

        self.mock_request.get_json.side_effect = Exception("Invalid JSON")
        result = gupshup_webhook()
        self.assertEqual(result["status"], "error")
        self.assertIn("Invalid JSON", result["message"])
        self.assertEqual(self.mock_response["http_status_code"], 400)

    def test_empty_payload_returns_400(self):
        from receivables_recovery.api import gupshup_webhook

        self.mock_request.get_json.return_value = None
        result = gupshup_webhook()
        self.assertEqual(result["status"], "error")
        self.assertIn("Empty", result["message"])

    def test_missing_id_returns_400(self):
        from receivables_recovery.api import gupshup_webhook

        self.mock_request.get_json.return_value = {
            "payload": {"type": "sent"}
        }
        result = gupshup_webhook()
        self.assertEqual(result["status"], "error")

    @patch("receivables_recovery.api.frappe.db.get_value")
    @patch("receivables_recovery.api.frappe.db.set_value")
    @patch("receivables_recovery.api.frappe.db.commit")
    def test_updates_status_sent(
        self, mock_commit, mock_set_value, mock_get_value
    ):
        from receivables_recovery.api import gupshup_webhook

        self.mock_request.get_json.return_value = {
            "payload": {
                "id": "gupshup-msg-123",
                "type": "sent",
            }
        }
        mock_get_value.return_value = "COMMLOG-0001"

        result = gupshup_webhook()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["new_status"], "Sent")
        mock_set_value.assert_called_with(
            "Communication Log", "COMMLOG-0001", "status", "Sent"
        )

    @patch("receivables_recovery.api.frappe.db.get_value")
    @patch("receivables_recovery.api.frappe.db.set_value")
    @patch("receivables_recovery.api.frappe.db.commit")
    def test_updates_status_delivered(
        self, mock_commit, mock_set_value, mock_get_value
    ):
        from receivables_recovery.api import gupshup_webhook

        self.mock_request.get_json.return_value = {
            "payload": {
                "id": "gupshup-msg-456",
                "type": "delivered",
            }
        }
        mock_get_value.return_value = "COMMLOG-0002"

        result = gupshup_webhook()

        self.assertEqual(result["new_status"], "Delivered")

    @patch("receivables_recovery.api.frappe.db.get_value")
    @patch("receivables_recovery.api.frappe.db.set_value")
    @patch("receivables_recovery.api.frappe.db.commit")
    def test_captures_error_on_failure(
        self, mock_commit, mock_set_value, mock_get_value
    ):
        from receivables_recovery.api import gupshup_webhook

        self.mock_request.get_json.return_value = {
            "payload": {
                "id": "gupshup-msg-789",
                "type": "failed",
                "error": {"code": 1001, "description": "Template not approved"},
            }
        }
        mock_get_value.return_value = "COMMLOG-0003"

        result = gupshup_webhook()

        self.assertEqual(result["new_status"], "Failed")

        # Should set both status and error_log
        set_value_calls = mock_set_value.call_args_list
        # First call: set_value(doctype, name, field, value)
        # Index [0] = args tuple, [2] = field name, [3] = field value
        self.assertEqual(
            set_value_calls[0][0][2], "status"
        )
        self.assertEqual(
            set_value_calls[0][0][3], "Failed"
        )

    @patch("receivables_recovery.api.frappe.db.get_value")
    @patch("receivables_recovery.api.frappe.db.set_value")
    @patch("receivables_recovery.api.frappe.db.commit")
    def test_handles_read_status(
        self, mock_commit, mock_set_value, mock_get_value
    ):
        from receivables_recovery.api import gupshup_webhook

        self.mock_request.get_json.return_value = {
            "payload": {
                "id": "gupshup-msg-101",
                "type": "read",
            }
        }
        mock_get_value.return_value = "COMMLOG-0004"

        result = gupshup_webhook()
        self.assertEqual(result["new_status"], "Read")

    @patch("receivables_recovery.api.frappe.db.get_value")
    @patch("receivables_recovery.api.frappe.db.set_value")
    @patch("receivables_recovery.api.frappe.db.commit")
    def test_no_log_found_returns_ok(
        self, mock_commit, mock_set_value, mock_get_value
    ):
        from receivables_recovery.api import gupshup_webhook

        self.mock_request.get_json.return_value = {
            "payload": {
                "id": "unknown-msg-id",
                "type": "delivered",
            }
        }
        mock_get_value.return_value = None  # No matching log

        result = gupshup_webhook()
        self.assertEqual(result["status"], "ok")
        # Should not call set_value if no log found
        mock_set_value.assert_not_called()


class TestMSG91Webhook(unittest.TestCase):
    """Tests for msg91_webhook()."""

    def setUp(self):
        self.request_patcher = patch(
            "receivables_recovery.api.frappe.request"
        )
        self.mock_request = self.request_patcher.start()

        self.response_patcher = patch(
            "receivables_recovery.api.frappe.response", new_callable=dict
        )
        self.mock_response = self.response_patcher.start()

    def tearDown(self):
        self.request_patcher.stop()
        self.response_patcher.stop()

    def test_missing_message_id_returns_400(self):
        from receivables_recovery.api import msg91_webhook

        self.mock_request.get_json.return_value = {"status": "DELIVRD"}
        result = msg91_webhook()
        self.assertEqual(result["status"], "error")
        self.assertIn("Missing", result["message"])

    @patch("receivables_recovery.api.frappe.db.get_value")
    @patch("receivables_recovery.api.frappe.db.set_value")
    @patch("receivables_recovery.api.frappe.db.commit")
    def test_delivered_status_mapping(
        self, mock_commit, mock_set_value, mock_get_value
    ):
        from receivables_recovery.api import msg91_webhook

        self.mock_request.get_json.return_value = {
            "message_id": "msg91-msg-001",
            "status": "DELIVRD",
        }
        mock_get_value.return_value = "COMMLOG-MSG91-001"

        result = msg91_webhook()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["new_status"], "Delivered")

    @patch("receivables_recovery.api.frappe.db.get_value")
    @patch("receivables_recovery.api.frappe.db.set_value")
    @patch("receivables_recovery.api.frappe.db.commit")
    def test_failed_status_mapping(
        self, mock_commit, mock_set_value, mock_get_value
    ):
        from receivables_recovery.api import msg91_webhook

        self.mock_request.get_json.return_value = {
            "message_id": "msg91-msg-002",
            "status": "UNDELIV",
            "error": "Destination unreachable",
        }
        mock_get_value.return_value = "COMMLOG-MSG91-002"

        result = msg91_webhook()

        self.assertEqual(result["new_status"], "Failed")

    @patch("receivables_recovery.api.frappe.db.get_value")
    @patch("receivables_recovery.api.frappe.db.set_value")
    @patch("receivables_recovery.api.frappe.db.commit")
    def test_unknown_status_defaults_to_sent(
        self, mock_commit, mock_set_value, mock_get_value
    ):
        from receivables_recovery.api import msg91_webhook

        self.mock_request.get_json.return_value = {
            "message_id": "msg91-msg-003",
            "status": "UNKNOWN_CODE",
        }
        mock_get_value.return_value = "COMMLOG-MSG91-003"

        result = msg91_webhook()

        # Unknown status defaults to "Sent"
        self.assertEqual(result["new_status"], "Sent")


class TestPermissionQueryConditions(unittest.TestCase):
    """Tests for get_permission_query_conditions_for_dunning()."""

    @patch("receivables_recovery.api.frappe.get_roles")
    def test_system_manager_sees_all(self, mock_get_roles):
        from receivables_recovery.api import get_permission_query_conditions_for_dunning

        mock_get_roles.return_value = ["System Manager"]
        result = get_permission_query_conditions_for_dunning("admin@example.com")
        self.assertEqual(result, "")  # Empty = no restriction

    @patch("receivables_recovery.api.frappe.get_roles")
    def test_collections_manager_sees_all(self, mock_get_roles):
        from receivables_recovery.api import get_permission_query_conditions_for_dunning

        mock_get_roles.return_value = ["Collections Manager"]
        result = get_permission_query_conditions_for_dunning("manager@example.com")
        self.assertEqual(result, "")

    @patch("receivables_recovery.api.frappe.get_roles")
    def test_sales_rep_has_restricted_query(self, mock_get_roles):
        from receivables_recovery.api import get_permission_query_conditions_for_dunning

        mock_get_roles.return_value = ["Sales Rep"]
        result = get_permission_query_conditions_for_dunning("rep@example.com")
        self.assertIn("custom_assigned_sales_rep", result)
        # SQL uses parameterized placeholder %(user)s for the user value
        self.assertIn("%(user)s", result)

    @patch("receivables_recovery.api.frappe.get_roles")
    def test_unknown_role_sees_nothing(self, mock_get_roles):
        from receivables_recovery.api import get_permission_query_conditions_for_dunning

        mock_get_roles.return_value = ["Blogger"]
        result = get_permission_query_conditions_for_dunning("blogger@example.com")
        self.assertEqual(result, "1=0")

    @patch("receivables_recovery.api.frappe.get_roles")
    @patch("receivables_recovery.api.frappe.session")
    def test_falls_back_to_session_user(
        self, mock_session, mock_get_roles
    ):
        from receivables_recovery.api import get_permission_query_conditions_for_dunning

        mock_session.user = "fallback@example.com"
        mock_get_roles.return_value = ["Sales Rep"]

        # Call with None user — should use session.user
        result = get_permission_query_conditions_for_dunning(None)
        # SQL uses parameterized placeholder %(user)s
        self.assertIn("%(user)s", result)


class TestHasDunningPermission(unittest.TestCase):
    """Tests for has_dunning_permission()."""

    def setUp(self):
        self.doc = make_mock_doc("Dunning", **MOCK_DUNNING)
        self.customer = make_mock_doc("Customer", **MOCK_CUSTOMER)

    @patch("receivables_recovery.api.frappe.get_roles")
    def test_system_manager_always_has_access(self, mock_get_roles):
        from receivables_recovery.api import has_dunning_permission

        mock_get_roles.return_value = ["System Manager"]
        result = has_dunning_permission(self.doc, "read", "admin@example.com")
        self.assertTrue(result)

    @patch("receivables_recovery.api.frappe.get_roles")
    def test_collections_manager_always_has_access(self, mock_get_roles):
        from receivables_recovery.api import has_dunning_permission

        mock_get_roles.return_value = ["Collections Manager"]
        result = has_dunning_permission(self.doc, "read", "manager@example.com")
        self.assertTrue(result)

    @patch("receivables_recovery.api.frappe.get_roles")
    @patch("receivables_recovery.api.frappe.get_doc")
    def test_sales_rep_has_access_for_assigned_customer(
        self, mock_get_doc, mock_get_roles
    ):
        from receivables_recovery.api import has_dunning_permission

        mock_get_roles.return_value = ["Sales Rep"]

        # Customer assigned to this sales rep
        assigned_customer = make_mock_doc(
            "Customer",
            customer_name="_Test Customer",
            custom_assigned_sales_rep="rep@example.com",
            owner="someone_else@example.com",
        )
        mock_get_doc.return_value = assigned_customer

        result = has_dunning_permission(
            self.doc, "read", "rep@example.com"
        )
        self.assertTrue(result)

    @patch("receivables_recovery.api.frappe.get_roles")
    @patch("receivables_recovery.api.frappe.get_doc")
    def test_sales_rep_denied_for_unassigned_customer(
        self, mock_get_doc, mock_get_roles
    ):
        from receivables_recovery.api import has_dunning_permission

        mock_get_roles.return_value = ["Sales Rep"]

        # Customer assigned to someone else
        other_customer = make_mock_doc(
            "Customer",
            customer_name="_Test Customer",
            custom_assigned_sales_rep="other_rep@example.com",
            owner="other_rep@example.com",
        )
        mock_get_doc.return_value = other_customer

        result = has_dunning_permission(
            self.doc, "read", "rep@example.com"
        )
        self.assertFalse(result)

    @patch("receivables_recovery.api.frappe.get_roles")
    @patch("receivables_recovery.api.frappe.get_doc")
    def test_sales_rep_has_access_as_owner_fallback(
        self, mock_get_doc, mock_get_roles
    ):
        from receivables_recovery.api import has_dunning_permission

        mock_get_roles.return_value = ["Sales Rep"]

        # No assigned rep, but user is the owner
        owner_customer = make_mock_doc(
            "Customer",
            customer_name="_Test Customer",
            custom_assigned_sales_rep=None,
            owner="owner_rep@example.com",
        )
        mock_get_doc.return_value = owner_customer

        result = has_dunning_permission(
            self.doc, "read", "owner_rep@example.com"
        )
        self.assertTrue(result)

    @patch("receivables_recovery.api.frappe.get_roles")
    def test_no_relevant_role_denied(self, mock_get_roles):
        from receivables_recovery.api import has_dunning_permission

        mock_get_roles.return_value = ["Guest"]
        result = has_dunning_permission(self.doc, "read", "guest@example.com")
        self.assertFalse(result)


class TestValidateDunning(unittest.TestCase):
    """Tests for validate_dunning()."""

    def setUp(self):
        self.doc = make_mock_doc("Dunning", **MOCK_DUNNING)

    @patch("receivables_recovery.api.frappe.session")
    @patch("receivables_recovery.api.frappe.get_roles")
    def test_throws_when_dispute_flag_without_reason(
        self, mock_get_roles, mock_session
    ):
        from receivables_recovery.api import validate_dunning

        self.doc.dispute_flag = 1
        self.doc.dispute_reason = ""
        mock_session.user = "admin@example.com"
        mock_get_roles.return_value = ["System Manager"]

        with self.assertRaises(Exception) as ctx:
            validate_dunning(self.doc, None)
        self.assertIn("Dispute Reason", str(ctx.exception))

    @patch("receivables_recovery.api.frappe.session")
    @patch("receivables_recovery.api.frappe.get_roles")
    def test_passes_when_dispute_flag_with_reason(
        self, mock_get_roles, mock_session
    ):
        from receivables_recovery.api import validate_dunning

        self.doc.dispute_flag = 1
        self.doc.dispute_reason = "Customer claims service not delivered"
        mock_session.user = "admin@example.com"
        mock_get_roles.return_value = ["System Manager"]

        try:
            validate_dunning(self.doc, None)
        except Exception:
            self.fail("validate_dunning raised unexpectedly")

    @patch("receivables_recovery.api.frappe.session")
    @patch("receivables_recovery.api.frappe.get_roles")
    @patch("receivables_recovery.api.frappe.log_error")
    def test_logs_escalation_change(
        self, mock_log_error, mock_get_roles, mock_session
    ):
        from receivables_recovery.api import validate_dunning

        # Simulate doc having a previous version
        doc_before = MagicMock()
        doc_before.get.return_value = "Reminder 1"
        self.doc.get_doc_before_save = MagicMock(return_value=doc_before)
        self.doc.escalation_stage = "Reminder 2"

        mock_session.user = "admin@example.com"
        mock_get_roles.return_value = ["System Manager"]

        validate_dunning(self.doc, None)

        # Should log the change
        mock_log_error.assert_called_once()
        args, _ = mock_log_error.call_args
        self.assertIn("Reminder 1", args[0])
        self.assertIn("Reminder 2", args[0])

    @patch("receivables_recovery.api.frappe.session")
    @patch("receivables_recovery.api.frappe.get_roles")
    def test_throws_when_sales_rep_changes_escalation(
        self, mock_get_roles, mock_session
    ):
        from receivables_recovery.api import validate_dunning

        doc_before = MagicMock()
        doc_before.get.return_value = "Reminder 1"
        self.doc.get_doc_before_save = MagicMock(return_value=doc_before)
        self.doc.escalation_stage = "Legal Referral"

        mock_session.user = "rep@example.com"
        mock_get_roles.return_value = ["Sales Rep"]

        with self.assertRaises(Exception) as ctx:
            validate_dunning(self.doc, None)
        self.assertIn("Escalation Stage", str(ctx.exception))

    @patch("receivables_recovery.api.frappe.session")
    @patch("receivables_recovery.api.frappe.get_roles")
    def test_sales_rep_can_update_last_contact(
        self, mock_get_roles, mock_session
    ):
        from receivables_recovery.api import validate_dunning

        doc_before = MagicMock()
        doc_before.get.return_value = "Reminder 1"
        self.doc.get_doc_before_save = MagicMock(return_value=doc_before)
        self.doc.escalation_stage = "Reminder 1"  # Same stage — OK
        self.doc.last_contact_channel = "Call"

        mock_session.user = "rep@example.com"
        mock_get_roles.return_value = ["Sales Rep"]

        try:
            validate_dunning(self.doc, None)
        except Exception:
            self.fail("Sales Rep should be able to update last_contact_channel")


if __name__ == "__main__":
    unittest.main()
