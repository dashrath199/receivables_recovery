# -*- coding: utf-8 -*-
"""Unit tests for receivables_recovery.messaging module.

Tests cover:
- build_template_values() — pure value mapping
- send_via_gupshup() — WhatsApp API integration with credential validation
- send_via_msg91() — SMS API integration with credential validation
- send_payment_reminder() — full flow with Communication Log creation
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
from unittest.mock import patch, MagicMock, call
import json


class TestBuildTemplateValues(unittest.TestCase):
    """Tests for build_template_values() — pure function."""

    def setUp(self):
        self.customer = MagicMock()
        self.customer.customer_name = "Acme Corp"
        self.invoice = MagicMock()
        self.invoice.name = "SINV-00001"
        self.invoice.outstanding_amount = 50000.00
        self.invoice.due_date = "2026-07-01"
        self.invoice.company = "_Test Company"

    @patch("receivables_recovery.messaging.date_diff")
    @patch("receivables_recovery.messaging.today")
    def test_basic_template_values(self, mock_today, mock_date_diff):
        from receivables_recovery.messaging import build_template_values

        mock_today.return_value = "2026-07-20"
        mock_date_diff.return_value = 19

        variables = [
            "customer_name",
            "invoice_no",
            "amount",
            "due_date",
            "days_overdue",
        ]
        result = build_template_values(self.customer, self.invoice, variables)

        self.assertEqual(result[0], "Acme Corp")
        self.assertEqual(result[1], "SINV-00001")
        self.assertEqual(result[2], "50000.0")
        self.assertEqual(result[3], "2026-07-01")
        self.assertEqual(result[4], "19")

    def test_unknown_variable_returns_empty_string(self):
        from receivables_recovery.messaging import build_template_values

        variables = ["nonexistent_field"]
        result = build_template_values(self.customer, self.invoice, variables)
        self.assertEqual(result, [""])

    def test_empty_variables_list(self):
        from receivables_recovery.messaging import build_template_values

        result = build_template_values(self.customer, self.invoice, [])
        self.assertEqual(result, [])

    def test_whitespace_in_variable_name(self):
        from receivables_recovery.messaging import build_template_values

        variables = ["  customer_name  "]
        result = build_template_values(self.customer, self.invoice, variables)
        self.assertEqual(result, ["Acme Corp"])

    def test_all_known_variables(self):
        from receivables_recovery.messaging import build_template_values

        self.invoice.outstanding_amount = 75000.00
        variables = [
            "customer_name",
            "invoice_no",
            "amount",
            "outstanding_amount",
            "due_date",
            "company",
        ]
        result = build_template_values(self.customer, self.invoice, variables)

        self.assertEqual(result[0], "Acme Corp")
        self.assertEqual(result[1], "SINV-00001")
        self.assertEqual(result[2], "75000.0")
        self.assertEqual(result[3], "75000.0")
        self.assertEqual(result[4], "2026-07-01")
        self.assertEqual(result[5], "_Test Company")


class TestSendViaGupshup(unittest.TestCase):
    """Tests for send_via_gupshup()."""

    @patch("receivables_recovery.messaging.requests.post")
    def test_sends_correct_payload(self, mock_post):
        from receivables_recovery.messaging import send_via_gupshup

        mock_response = MagicMock()
        mock_response.json.return_value = {"messageId": "gupshup-msg-123"}
        mock_post.return_value = mock_response

        with patch.multiple(
            "receivables_recovery.messaging.frappe.conf",
            gupshup_api_key="test-key",
            gupshup_source_number="+14151234567",
            gupshup_app_name="TestApp",
        ):
            result = send_via_gupshup(
                to_number="+919999999999",
                template_id="payment_due_reminder_en",
                values=["Acme Corp", "SINV-001", "50000", "2026-07-01", "19"],
            )

        self.assertEqual(result["messageId"], "gupshup-msg-123")

        # Verify the POST call
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        self.assertIn("gupshup.io", url)
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers["apikey"], "test-key")
        data = mock_post.call_args[1]["data"]
        self.assertIn("+919999999999", data["destination"])

    @patch("receivables_recovery.messaging.requests.post")
    def test_raises_error_when_credentials_missing(self, mock_post):
        from receivables_recovery.messaging import send_via_gupshup

        with patch.multiple(
            "receivables_recovery.messaging.frappe.conf",
            gupshup_api_key=None,
            gupshup_source_number=None,
            gupshup_app_name=None,
        ):
            with self.assertRaises(Exception) as ctx:
                send_via_gupshup(
                    to_number="+919999999999",
                    template_id="test-template",
                    values=["value1"],
                )
            self.assertIn("credentials", str(ctx.exception).lower())

    @patch("receivables_recovery.messaging.requests.post")
    def test_raises_on_http_error(self, mock_post):
        from receivables_recovery.messaging import send_via_gupshup
        import requests

        mock_post.side_effect = requests.exceptions.HTTPError(
            "401 Client Error"
        )

        with patch.multiple(
            "receivables_recovery.messaging.frappe.conf",
            gupshup_api_key="test-key",
            gupshup_source_number="+14151234567",
            gupshup_app_name="TestApp",
        ):
            with self.assertRaises(requests.exceptions.HTTPError):
                send_via_gupshup(
                    to_number="+919999999999",
                    template_id="test-template",
                    values=["value1"],
                )


class TestSendViaMSG91(unittest.TestCase):
    """Tests for send_via_msg91()."""

    @patch("receivables_recovery.messaging.requests.post")
    def test_sends_correct_payload(self, mock_post):
        from receivables_recovery.messaging import send_via_msg91

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message_id": "msg91-msg-123",
            "request_id": "req-456",
        }
        mock_post.return_value = mock_response

        with patch.multiple(
            "receivables_recovery.messaging.frappe.conf",
            msg91_auth_key="test-auth-key",
            msg91_sender_id="TESTSMS",
        ):
            result = send_via_msg91(
                to_number="+919999999999",
                body_text="Dear {}, your invoice {} is due.",
                values=["Acme Corp", "SINV-001"],
            )

        self.assertEqual(result["message_id"], "msg91-msg-123")

        # Verify POST call details
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        self.assertIn("msg91.com", url)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["sender"], "TESTSMS")
        self.assertEqual(payload["mobiles"], "+919999999999")

    def test_substitutes_placeholders_positionally(self):
        """Test the positional replacement logic."""
        from receivables_recovery.messaging import send_via_msg91

        mock_response = MagicMock()
        mock_response.json.return_value = {"message_id": "test-id"}

        with patch(
            "receivables_recovery.messaging.requests.post",
            return_value=mock_response,
        ) as mock_post:
            with patch.multiple(
                "receivables_recovery.messaging.frappe.conf",
                msg91_auth_key="test-key",
                msg91_sender_id="TEST",
            ):
                send_via_msg91(
                    to_number="+919999999999",
                    body_text="Hello {}, invoice {} amount {}.",
                    values=["John", "INV-001", "5000"],
                )

            payload = mock_post.call_args[1]["json"]
            self.assertIn("Hello John", payload["message"])
            self.assertIn("invoice INV-001", payload["message"])
            self.assertIn("amount 5000", payload["message"])

    @patch("receivables_recovery.messaging.requests.post")
    def test_raises_error_when_credentials_missing(self, mock_post):
        from receivables_recovery.messaging import send_via_msg91

        with patch.multiple(
            "receivables_recovery.messaging.frappe.conf",
            msg91_auth_key=None,
            msg91_sender_id=None,
        ):
            with self.assertRaises(Exception) as ctx:
                send_via_msg91(
                    to_number="+919999999999",
                    body_text="Test {}",
                    values=["value"],
                )
            self.assertIn("credentials", str(ctx.exception).lower())


class TestSendPaymentReminder(unittest.TestCase):
    """Tests for send_payment_reminder() — the orchestrator function.

    Uses a single side_effect function for frappe.get_doc to handle
    both document lookups (Dunning, Customer, Message Template, Sales Invoice)
    and document creation (Communication Log) with a single mock.
    """

    def setUp(self):
        self.dunning = make_mock_doc("Dunning", **MOCK_DUNNING)
        self.customer = make_mock_doc("Customer", **MOCK_CUSTOMER)
        self.invoice = make_mock_doc("Sales Invoice", **MOCK_SALES_INVOICE)
        self.template = make_mock_doc("Message Template", **MOCK_MESSAGE_TEMPLATE)

    def _make_get_doc_side_effect(self, comm_log=None):
        """Create a side_effect function for frappe.get_doc.

        Maps doctype strings to the corresponding mock objects.
        For dict-based calls (Communication Log creation), returns the
        provided comm_log mock or creates a default one.
        """
        if comm_log is None:
            comm_log = make_mock_doc("Communication Log", **MOCK_COMM_LOG)
            comm_log.name = "COMMLOG-NEW-001"
            comm_log.insert = MagicMock()

        def side_effect(doctype_or_dict, *args, **kwargs):
            # Handle dict-based call (doc creation)
            if isinstance(doctype_or_dict, dict):
                if doctype_or_dict.get("doctype") == "Communication Log":
                    return comm_log
                # Fallback for other creation calls
                doc = make_mock_doc(doctype_or_dict.get("doctype", "Unknown"))
                doc.insert = MagicMock()
                return doc

            # Handle string-based call (doc lookup)
            doctype = doctype_or_dict
            docname = args[0] if args else kwargs.get("name", "")
            mapping = {
                "Dunning": self.dunning,
                "Customer": self.customer,
                "Sales Invoice": self.invoice,
                "Message Template": self.template,
            }
            return mapping.get(doctype, make_mock_doc(doctype, name=docname))

        return side_effect

    @patch("receivables_recovery.messaging.frappe.db.commit")
    @patch("receivables_recovery.messaging.frappe.db.set_value")
    @patch("receivables_recovery.messaging.frappe.log_error")
    @patch("receivables_recovery.messaging.send_via_gupshup")
    @patch("receivables_recovery.messaging.frappe.utils.now")
    @patch("receivables_recovery.messaging.frappe.get_doc")
    def test_successful_whatsapp_send(
        self,
        mock_get_doc,
        mock_now,
        mock_send_via,
        mock_log_error,
        mock_set_value,
        mock_commit,
    ):
        from receivables_recovery.messaging import send_payment_reminder

        mock_comm_log = make_mock_doc("Communication Log", **MOCK_COMM_LOG)
        mock_comm_log.name = "COMMLOG-WA-001"
        mock_comm_log.insert = MagicMock()

        mock_get_doc.side_effect = self._make_get_doc_side_effect(
            comm_log=mock_comm_log
        )
        mock_send_via.return_value = {"messageId": "gupshup-msg-12345"}
        mock_now.return_value = "2026-07-20 10:00:00"

        result = send_payment_reminder(
            "DUNN-0001", "WhatsApp", "payment_due_reminder_en"
        )

        self.assertEqual(result["status"], "Sent")
        self.assertEqual(
            result["provider_message_id"], "gupshup-msg-12345"
        )
        self.assertEqual(
            result["communication_log"], "COMMLOG-WA-001"
        )

        # Verify the Communication Log was inserted
        mock_comm_log.insert.assert_called_once_with(
            ignore_permissions=True
        )

        # Verify the provider API was called with correct args
        mock_send_via.assert_called_once()
        call_kwargs = mock_send_via.call_args[1]
        self.assertEqual(
            call_kwargs["to_number"], MOCK_CUSTOMER["whatsapp_number"]
        )
        self.assertEqual(
            call_kwargs["template_id"],
            MOCK_MESSAGE_TEMPLATE["whatsapp_template_id"],
        )

        # Verify db updates were made
        # First set_value updates Communication Log status + provider_message_id
        # Second set_value updates Dunning's last_contact_channel
        self.assertEqual(mock_set_value.call_count, 2)

    @patch("receivables_recovery.messaging.frappe.db.commit")
    @patch("receivables_recovery.messaging.frappe.db.set_value")
    @patch("receivables_recovery.messaging.frappe.log_error")
    @patch("receivables_recovery.messaging.send_via_msg91")
    @patch("receivables_recovery.messaging.frappe.utils.now")
    @patch("receivables_recovery.messaging.frappe.get_doc")
    def test_successful_sms_send(
        self,
        mock_get_doc,
        mock_now,
        mock_send_via,
        mock_log_error,
        mock_set_value,
        mock_commit,
    ):
        from receivables_recovery.messaging import send_payment_reminder

        mock_comm_log = make_mock_doc("Communication Log", **MOCK_COMM_LOG)
        mock_comm_log.name = "COMMLOG-SMS-001"
        mock_comm_log.insert = MagicMock()

        mock_get_doc.side_effect = self._make_get_doc_side_effect(
            comm_log=mock_comm_log
        )
        mock_send_via.return_value = {"message_id": "msg91-msg-999"}
        mock_now.return_value = "2026-07-20 10:00:00"

        result = send_payment_reminder(
            "DUNN-0001", "SMS", "payment_due_reminder_en"
        )

        self.assertEqual(result["status"], "Sent")
        self.assertEqual(
            result["communication_log"], "COMMLOG-SMS-001"
        )

        # Verify SMS API was called with customer's SMS number
        mock_send_via.assert_called_once()
        call_kwargs = mock_send_via.call_args[1]
        self.assertEqual(
            call_kwargs["to_number"], MOCK_CUSTOMER["sms_number"]
        )

    @patch("receivables_recovery.messaging.frappe.db.commit")
    @patch("receivables_recovery.messaging.frappe.db.set_value")
    @patch("receivables_recovery.messaging.frappe.log_error")
    @patch("receivables_recovery.messaging.send_via_gupshup")
    @patch("receivables_recovery.messaging.frappe.utils.now")
    @patch("receivables_recovery.messaging.frappe.get_doc")
    def test_failure_creates_comm_log_with_error(
        self,
        mock_get_doc,
        mock_now,
        mock_send_via,
        mock_log_error,
        mock_set_value,
        mock_commit,
    ):
        from receivables_recovery.messaging import send_payment_reminder

        mock_comm_log = make_mock_doc("Communication Log", **MOCK_COMM_LOG)
        mock_comm_log.name = "COMMLOG-FAIL-001"
        mock_comm_log.insert = MagicMock()

        mock_get_doc.side_effect = self._make_get_doc_side_effect(
            comm_log=mock_comm_log
        )
        mock_send_via.side_effect = Exception(
            "HTTP 401: Unauthorized — Invalid Gupshup API key"
        )
        mock_now.return_value = "2026-07-20 10:00:00"

        result = send_payment_reminder(
            "DUNN-0001", "WhatsApp", "payment_due_reminder_en"
        )

        self.assertEqual(result["status"], "Failed")
        self.assertIn("401", result["error"])
        self.assertEqual(
            result["communication_log"], "COMMLOG-FAIL-001"
        )

        # Error should be logged
        mock_log_error.assert_called_once()
        args, _ = mock_log_error.call_args
        self.assertIn("HTTP 401", args[0])
        self.assertIn("Receivables Recovery — Messaging", args[1])

        # Communication Log should have been inserted
        mock_comm_log.insert.assert_called_once_with(
            ignore_permissions=True
        )


class TestBuildTemplateValuesWithRealData(unittest.TestCase):
    """Integration-like tests for build_template_values with realistic data."""

    @patch("receivables_recovery.messaging.date_diff")
    @patch("receivables_recovery.messaging.today")
    def test_matches_template_variables_order(
        self, mock_today, mock_date_diff
    ):
        """Verify the values array matches the expected order from the template."""
        from receivables_recovery.messaging import build_template_values

        mock_today.return_value = "2026-07-20"
        mock_date_diff.return_value = 155  # Delta Manufacturing — 150+ days overdue

        customer = MagicMock()
        customer.customer_name = "Delta Manufacturing"
        invoice = MagicMock()
        invoice.name = "SINV-2026-0001"
        invoice.outstanding_amount = 185000.00
        invoice.due_date = "2026-02-15"
        invoice.company = "My Company"

        # This is the variables_order from payment_due_reminder_en
        variables = [
            "customer_name",
            "invoice_no",
            "amount",
            "due_date",
            "days_overdue",
        ]
        values = build_template_values(customer, invoice, variables)

        self.assertEqual(len(values), 5)
        self.assertEqual(values[0], "Delta Manufacturing")
        self.assertEqual(values[1], "SINV-2026-0001")
        self.assertEqual(values[2], "185000.0")
        self.assertEqual(values[3], "2026-02-15")
        self.assertEqual(values[4], "155")  # Deterministic now — mocked


class TestSendPaymentReminderEdgeCases(unittest.TestCase):
    """Edge case tests for send_payment_reminder."""

    def test_unsupported_channel_returns_failed(self):
        """Test that unsupported channel results in a Failed status."""
        from receivables_recovery.messaging import send_payment_reminder

        mock_dunning = make_mock_doc("Dunning", **MOCK_DUNNING)
        mock_customer = make_mock_doc("Customer", **MOCK_CUSTOMER)
        mock_template = make_mock_doc("Message Template", **MOCK_MESSAGE_TEMPLATE)
        mock_invoice = make_mock_doc("Sales Invoice", **MOCK_SALES_INVOICE)

        def get_doc_side_effect(doctype_or_dict, *args, **kwargs):
            if isinstance(doctype_or_dict, dict):
                log = make_mock_doc("Communication Log", **MOCK_COMM_LOG)
                log.name = "COMMLOG-ERR-001"
                log.insert = MagicMock()
                return log
            mapping = {
                "Dunning": mock_dunning,
                "Customer": mock_customer,
                "Message Template": mock_template,
                "Sales Invoice": mock_invoice,
            }
            return mapping.get(doctype_or_dict, MagicMock())

        with patch(
            "receivables_recovery.messaging.frappe.get_doc",
            side_effect=get_doc_side_effect,
        ):
            with patch(
                "receivables_recovery.messaging.frappe.db.set_value"
            ):
                with patch(
                    "receivables_recovery.messaging.frappe.db.commit"
                ):
                    with patch(
                        "receivables_recovery.messaging.frappe.log_error"
                    ):
                        result = send_payment_reminder(
                            "DUNN-0001", "Email", "some_template"
                        )

        self.assertEqual(result["status"], "Failed")
        self.assertIn("Unsupported channel", result["error"])


if __name__ == "__main__":
    unittest.main()
