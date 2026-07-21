# -*- coding: utf-8 -*-
"""Unit tests for receivables_recovery.tasks module.

All Frappe dependencies are mocked. Tests can run standalone with pytest
or on a Frappe bench with `bench run-tests`.
"""
from __future__ import unicode_literals
import sys
from pathlib import Path

# Must import test_setup BEFORE any receivables_recovery source modules
# so frappe is mocked before the source modules are loaded
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from test_setup import *  # noqa: F403, F401 — mocks frappe via sys.modules
from test_helpers import *  # noqa: F403, F401

import unittest
from unittest.mock import patch, MagicMock


class TestGetEscalationStage(unittest.TestCase):
    """Tests for get_escalation_stage_for_days() — pure function, no mocks needed."""

    def test_reminder_1_for_0_to_30_days(self):
        from receivables_recovery.tasks import get_escalation_stage_for_days
        for days in [0, 1, 15, 30]:
            with self.subTest(days=days):
                self.assertEqual(
                    get_escalation_stage_for_days(days), "Reminder 1"
                )

    def test_reminder_2_for_31_to_60_days(self):
        from receivables_recovery.tasks import get_escalation_stage_for_days
        for days in [31, 45, 60]:
            with self.subTest(days=days):
                self.assertEqual(
                    get_escalation_stage_for_days(days), "Reminder 2"
                )

    def test_final_notice_for_61_to_90_days(self):
        from receivables_recovery.tasks import get_escalation_stage_for_days
        for days in [61, 75, 90]:
            with self.subTest(days=days):
                self.assertEqual(
                    get_escalation_stage_for_days(days), "Final Notice"
                )

    def test_legal_referral_for_91_plus_days(self):
        from receivables_recovery.tasks import get_escalation_stage_for_days
        for days in [91, 120, 999]:
            with self.subTest(days=days):
                self.assertEqual(
                    get_escalation_stage_for_days(days), "Legal Referral"
                )

    def test_zero_days(self):
        from receivables_recovery.tasks import get_escalation_stage_for_days
        self.assertEqual(get_escalation_stage_for_days(0), "Reminder 1")

    def test_negative_days(self):
        from receivables_recovery.tasks import get_escalation_stage_for_days
        # Invoice not overdue yet — edge case
        self.assertEqual(get_escalation_stage_for_days(-1), "Reminder 1")


class TestAlreadySentToday(unittest.TestCase):
    """Tests for already_sent_today()."""

    @patch("receivables_recovery.tasks.frappe.db.exists")
    def test_returns_true_when_log_exists(self, mock_exists):
        from receivables_recovery.tasks import already_sent_today
        mock_exists.return_value = "COMMLOG-0001"
        self.assertTrue(already_sent_today("DUNN-0001"))

    @patch("receivables_recovery.tasks.frappe.db.exists")
    def test_returns_false_when_no_log(self, mock_exists):
        from receivables_recovery.tasks import already_sent_today
        mock_exists.return_value = None
        self.assertFalse(already_sent_today("DUNN-0001"))

    @patch("receivables_recovery.tasks.frappe.db.exists")
    def test_passes_correct_filters(self, mock_exists):
        from receivables_recovery.tasks import already_sent_today
        from frappe.utils import today
        already_sent_today("DUNN-0001")
        mock_exists.assert_called_once_with(
            "Communication Log",
            {"dunning": "DUNN-0001", "sent_on": [">=", today()]},
        )


class TestGetOrCreateDunning(unittest.TestCase):
    """Tests for get_or_create_dunning()."""

    @patch("receivables_recovery.tasks.frappe.db.get_value")
    def test_returns_existing_dunning(self, mock_get_value):
        from receivables_recovery.tasks import get_or_create_dunning
        mock_get_value.return_value = "DUNN-0001"

        mock_dunning = MagicMock()
        mock_dunning.name = "DUNN-0001"
        mock_dunning.escalation_stage = "Reminder 1"

        with patch(
            "receivables_recovery.tasks.frappe.get_doc",
            return_value=mock_dunning,
        ):
            result = get_or_create_dunning(
                MagicMock(name="SINV-0001", customer="_Test Customer"),
                days_overdue=5,
            )
            self.assertEqual(result.name, "DUNN-0001")

    @patch("receivables_recovery.tasks.frappe.db.get_value")
    def test_creates_new_dunning_when_not_exists(self, mock_get_value):
        from receivables_recovery.tasks import get_or_create_dunning
        mock_get_value.return_value = None

        mock_new_doc = MagicMock()
        mock_new_doc.name = "DUNN-NEW-001"

        invoice = MagicMock()
        invoice.name = "SINV-0001"
        invoice.customer = "_Test Customer"

        with patch(
            "receivables_recovery.tasks.frappe.get_doc",
            return_value=mock_new_doc,
        ):
            result = get_or_create_dunning(invoice, days_overdue=5)
            self.assertEqual(result.name, "DUNN-NEW-001")
            mock_new_doc.insert.assert_called_once_with(
                ignore_permissions=True
            )

    @patch("receivables_recovery.tasks.frappe.db.get_value")
    def test_creates_with_correct_escalation_stage(self, mock_get_value):
        from receivables_recovery.tasks import get_or_create_dunning
        mock_get_value.return_value = None

        invoice = MagicMock()
        invoice.name = "SINV-0001"
        invoice.customer = "_Test Customer"

        with patch(
            "receivables_recovery.tasks.frappe.get_doc"
        ) as mock_get_doc:
            mock_new_doc = MagicMock()
            mock_get_doc.return_value = mock_new_doc

            get_or_create_dunning(invoice, days_overdue=45)
            args, _ = mock_get_doc.call_args
            self.assertEqual(args[0]["escalation_stage"], "Reminder 2")

    @patch("receivables_recovery.tasks.frappe.db.get_value")
    def test_updates_escalation_stage_on_existing(self, mock_get_value):
        from receivables_recovery.tasks import get_or_create_dunning
        mock_get_value.return_value = "DUNN-0001"

        mock_dunning = MagicMock()
        mock_dunning.name = "DUNN-0001"
        mock_dunning.escalation_stage = "Reminder 1"  # old stage

        with patch(
            "receivables_recovery.tasks.frappe.get_doc",
            return_value=mock_dunning,
        ):
            invoice = MagicMock(name="SINV-0001")
            get_or_create_dunning(invoice, days_overdue=75)
            # Should update to Final Notice for 75 days
            mock_dunning.db_set.assert_called_once_with(
                "escalation_stage", "Final Notice"
            )


class TestFlagForCall(unittest.TestCase):
    """Tests for flag_for_call()."""

    @patch("receivables_recovery.tasks.frappe.msgprint")
    @patch("receivables_recovery.tasks.frappe.get_doc")
    def test_creates_todo_and_updates_channel(
        self, mock_get_doc, mock_msgprint
    ):
        from receivables_recovery.tasks import flag_for_call

        mock_dunning = MagicMock()
        mock_dunning.name = "DUNN-0001"
        mock_dunning.customer = "_Test Customer"
        mock_dunning.sales_invoice = "SINV-0001"
        mock_dunning.total_dunning = 50000.00

        mock_customer = MagicMock()
        mock_customer.custom_assigned_sales_rep = "sales_rep@example.com"
        mock_customer.owner = "Administrator"

        # get_doc returns dunning first, then customer, then todo
        mock_get_doc.side_effect = [mock_dunning, mock_customer, MagicMock()]

        flag_for_call("DUNN-0001")

        # Verify db_set was called
        mock_dunning.db_set.assert_called_once_with(
            "last_contact_channel", "Call"
        )
        # Verify a ToDo was created
        todo_call = mock_get_doc.call_args_list[-1][0][0]
        self.assertEqual(todo_call["doctype"], "ToDo")
        self.assertEqual(todo_call["reference_name"], "DUNN-0001")
        self.assertEqual(
            todo_call["owner"], "sales_rep@example.com"
        )

    @patch("receivables_recovery.tasks.frappe.msgprint")
    @patch("receivables_recovery.tasks.frappe.get_doc")
    def test_falls_back_to_owner_when_no_sales_rep(
        self, mock_get_doc, mock_msgprint
    ):
        from receivables_recovery.tasks import flag_for_call

        mock_dunning = MagicMock()
        mock_dunning.name = "DUNN-0001"
        mock_dunning.customer = "_Test Customer"
        mock_dunning.sales_invoice = "SINV-0001"

        mock_customer = MagicMock()
        # Simulate missing custom field
        mock_customer.custom_assigned_sales_rep = None
        mock_customer.owner = "original_owner@example.com"

        mock_get_doc.side_effect = [mock_dunning, mock_customer, MagicMock()]

        flag_for_call("DUNN-0001")

        todo_call = mock_get_doc.call_args_list[-1][0][0]
        self.assertEqual(todo_call["owner"], "original_owner@example.com")


class TestEscalateToLegal(unittest.TestCase):
    """Tests for escalate_to_legal()."""

    @patch("receivables_recovery.tasks.frappe.log_error")
    @patch("receivables_recovery.tasks.frappe.get_doc")
    def test_escalates_and_logs(self, mock_get_doc, mock_log_error):
        from receivables_recovery.tasks import escalate_to_legal

        mock_dunning = MagicMock()
        mock_dunning.name = "DUNN-0001"
        mock_dunning.customer = "_Test Customer"
        mock_dunning.sales_invoice = "SINV-0001"
        mock_get_doc.return_value = mock_dunning

        escalate_to_legal("DUNN-0001")

        mock_dunning.db_set.assert_called_once_with(
            "escalation_stage", "Legal Referral"
        )
        mock_log_error.assert_called_once()
        args, _ = mock_log_error.call_args
        self.assertIn("Legal Referral", args[0])
        self.assertIn("DUNN-0001", args[0])


class TestRunCollectionsCadence(unittest.TestCase):
    """Tests for run_collections_cadence()."""

    @patch("receivables_recovery.tasks.frappe.log_error")
    @patch("receivables_recovery.tasks.frappe.get_all")
    def test_logs_warning_when_no_overdue_invoices(
        self, mock_get_all, mock_log_error
    ):
        from receivables_recovery.tasks import run_collections_cadence
        mock_get_all.return_value = []
        run_collections_cadence()
        mock_log_error.assert_called_once()

    @patch("receivables_recovery.tasks.flag_for_call")
    @patch("receivables_recovery.tasks.already_sent_today")
    @patch("receivables_recovery.tasks.get_or_create_dunning")
    @patch("receivables_recovery.tasks.frappe.db.get_value")
    @patch("receivables_recovery.tasks.frappe.get_all")
    def test_sends_whatsapp_for_rule_action(
        self,
        mock_get_all,
        mock_get_value,
        mock_get_or_create,
        mock_already_sent,
        mock_flag_for_call,
    ):
        from receivables_recovery.tasks import run_collections_cadence

        # Mock overdue invoice
        mock_invoice = MagicMock()
        mock_invoice.name = "SINV-0001"
        mock_invoice.customer = "_Test Customer"
        mock_invoice.due_date = "2026-07-01"
        mock_get_all.return_value = [mock_invoice]

        # Mock cadence rule — use MockFrappeDict for attribute access (rule.action)
        mock_get_value.return_value = MockFrappeDict({
            "name": "CADENCE-0001",
            "action": "Send WhatsApp Reminder",
            "message_template": "payment_due_reminder_en",
        })

        # Mock dunning
        mock_dunning = MagicMock()
        mock_dunning.name = "DUNN-0001"
        mock_dunning.dispute_flag = False
        mock_get_or_create.return_value = mock_dunning

        # Not already sent
        mock_already_sent.return_value = False

        with patch(
            "receivables_recovery.tasks.send_payment_reminder"
        ) as mock_send:
            run_collections_cadence()
            mock_send.assert_called_once_with(
                "DUNN-0001", "WhatsApp", "payment_due_reminder_en"
            )

    @patch("receivables_recovery.tasks.flag_for_call")
    @patch("receivables_recovery.tasks.escalate_to_legal")
    @patch("receivables_recovery.tasks.already_sent_today")
    @patch("receivables_recovery.tasks.get_or_create_dunning")
    @patch("receivables_recovery.tasks.frappe.db.get_value")
    @patch("receivables_recovery.tasks.frappe.get_all")
    def test_flag_for_call_action(
        self,
        mock_get_all,
        mock_get_value,
        mock_get_or_create,
        mock_already_sent,
        mock_escalate,
        mock_flag,
    ):
        from receivables_recovery.tasks import run_collections_cadence

        mock_invoice = MagicMock()
        mock_invoice.name = "SINV-0001"
        mock_invoice.customer = "_Test Customer"
        mock_invoice.due_date = "2026-07-01"
        mock_get_all.return_value = [mock_invoice]

        mock_get_value.return_value = MockFrappeDict({
            "name": "CADENCE-0002",
            "action": "Flag for Call",
            "message_template": "",
        })

        mock_dunning = MagicMock()
        mock_dunning.name = "DUNN-0001"
        mock_dunning.dispute_flag = False
        mock_get_or_create.return_value = mock_dunning
        mock_already_sent.return_value = False

        run_collections_cadence()
        mock_flag.assert_called_once_with("DUNN-0001")
        mock_escalate.assert_not_called()

    @patch("receivables_recovery.tasks.already_sent_today")
    @patch("receivables_recovery.tasks.get_or_create_dunning")
    @patch("receivables_recovery.tasks.frappe.db.get_value")
    @patch("receivables_recovery.tasks.frappe.get_all")
    def test_skips_disputed_invoices(
        self,
        mock_get_all,
        mock_get_value,
        mock_get_or_create,
        mock_already_sent,
    ):
        from receivables_recovery.tasks import run_collections_cadence

        mock_invoice = MagicMock()
        mock_invoice.name = "SINV-0001"
        mock_invoice.customer = "_Test Customer"
        mock_invoice.due_date = "2026-07-01"
        mock_get_all.return_value = [mock_invoice]

        mock_get_value.return_value = MockFrappeDict({
            "name": "CADENCE-0001",
            "action": "Send WhatsApp Reminder",
            "message_template": "payment_due_reminder_en",
        })

        mock_dunning = MagicMock()
        mock_dunning.dispute_flag = True  # Disputed!
        mock_get_or_create.return_value = mock_dunning
        mock_already_sent.return_value = False

        with patch(
            "receivables_recovery.tasks.send_payment_reminder"
        ) as mock_send:
            run_collections_cadence()
            mock_send.assert_not_called()

    @patch("receivables_recovery.tasks.already_sent_today")
    @patch("receivables_recovery.tasks.get_or_create_dunning")
    @patch("receivables_recovery.tasks.frappe.db.get_value")
    @patch("receivables_recovery.tasks.frappe.get_all")
    def test_skips_if_already_sent_today(
        self,
        mock_get_all,
        mock_get_value,
        mock_get_or_create,
        mock_already_sent,
    ):
        from receivables_recovery.tasks import run_collections_cadence

        mock_invoice = MagicMock()
        mock_invoice.name = "SINV-0001"
        mock_invoice.customer = "_Test Customer"
        mock_invoice.due_date = "2026-07-01"
        mock_get_all.return_value = [mock_invoice]

        mock_get_value.return_value = MockFrappeDict({
            "name": "CADENCE-0001",
            "action": "Send WhatsApp Reminder",
            "message_template": "payment_due_reminder_en",
        })

        mock_dunning = MagicMock()
        mock_dunning.dispute_flag = False
        mock_get_or_create.return_value = mock_dunning
        mock_already_sent.return_value = True  # Already sent

        with patch(
            "receivables_recovery.tasks.send_payment_reminder"
        ) as mock_send:
            run_collections_cadence()
            mock_send.assert_not_called()


class TestCheckBrokenPromises(unittest.TestCase):
    """Tests for check_broken_promises()."""

    @patch("receivables_recovery.tasks.frappe.db.sql")
    @patch("receivables_recovery.tasks.frappe.db.set_value")
    def test_no_broken_promises(self, mock_set_value, mock_sql):
        from receivables_recovery.tasks import check_broken_promises
        mock_sql.return_value = []
        check_broken_promises()
        mock_set_value.assert_not_called()

    @patch("receivables_recovery.tasks.frappe.db.sql")
    @patch("receivables_recovery.tasks.frappe.db.set_value")
    @patch("receivables_recovery.tasks.frappe.get_doc")
    def test_updates_stage_and_creates_notification(
        self, mock_get_doc, mock_set_value, mock_sql
    ):
        from receivables_recovery.tasks import check_broken_promises

        mock_sql.return_value = [
            MockFrappeDict({
                "dunning_name": "DUNN-0001",
                "customer": "_Test Customer",
                "sales_invoice": "SINV-0001",
                "promised_payment_date": "2026-07-01",
                "escalation_stage": "Final Notice",
            })
        ]
        mock_notification = MagicMock()
        mock_get_doc.return_value = mock_notification

        check_broken_promises()

        mock_set_value.assert_called_once_with(
            "Dunning", "DUNN-0001", "escalation_stage", "Final Notice"
        )
        mock_notification.insert.assert_called_once_with(
            ignore_permissions=True
        )


class TestRetryFailedMessages(unittest.TestCase):
    """Tests for retry_failed_messages()."""

    @patch("receivables_recovery.tasks.frappe.get_all")
    @patch("receivables_recovery.tasks.frappe.db.set_value")
    def test_no_failed_messages(self, mock_set_value, mock_get_all):
        from receivables_recovery.tasks import retry_failed_messages
        mock_get_all.return_value = []
        retry_failed_messages()
        mock_set_value.assert_not_called()

    @patch("receivables_recovery.tasks.send_payment_reminder")
    @patch("receivables_recovery.tasks.frappe.db.set_value")
    @patch("receivables_recovery.tasks.frappe.get_doc")
    @patch("receivables_recovery.tasks.frappe.get_all")
    def test_retries_failed_message(
        self,
        mock_get_all,
        mock_get_doc,
        mock_set_value,
        mock_send_reminder,
    ):
        from receivables_recovery.tasks import retry_failed_messages

        mock_get_all.return_value = [
            MockFrappeDict({
                "name": "COMMLOG-0001",
                "dunning": "DUNN-0001",
                "channel": "WhatsApp",
                "message_template": "payment_due_reminder_en",
            })
        ]
        mock_dunning = MagicMock()
        mock_dunning.dispute_flag = False
        mock_get_doc.return_value = mock_dunning

        retry_failed_messages()

        mock_send_reminder.assert_called_once_with(
            "DUNN-0001", "WhatsApp", "payment_due_reminder_en"
        )
        # Check status was reset to Queued
        mock_set_value.assert_called_with(
            "Communication Log", "COMMLOG-0001", "status", "Queued"
        )

    @patch("receivables_recovery.tasks.send_payment_reminder")
    @patch("receivables_recovery.tasks.frappe.db.set_value")
    @patch("receivables_recovery.tasks.frappe.get_doc")
    @patch("receivables_recovery.tasks.frappe.get_all")
    def test_skips_disputed_dunning_on_retry(
        self,
        mock_get_all,
        mock_get_doc,
        mock_set_value,
        mock_send_reminder,
    ):
        from receivables_recovery.tasks import retry_failed_messages

        mock_get_all.return_value = [
            MockFrappeDict({
                "name": "COMMLOG-0001",
                "dunning": "DUNN-0001",
                "channel": "WhatsApp",
                "message_template": "payment_due_reminder_en",
            })
        ]
        mock_dunning = MagicMock()
        mock_dunning.dispute_flag = True  # Disputed — skip retry
        mock_get_doc.return_value = mock_dunning

        retry_failed_messages()

        mock_send_reminder.assert_not_called()
        mock_set_value.assert_not_called()


if __name__ == "__main__":
    unittest.main()
