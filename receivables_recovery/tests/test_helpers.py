# -*- coding: utf-8 -*-
"""Shared test helpers, fixtures, and mock data for unit tests.

All tests use `unittest.mock` to isolate Frappe dependencies.
To run on a Frappe bench instead (integration tests), use:
    bench run-tests --module receivables_recovery.tests
"""
from __future__ import unicode_literals
from unittest.mock import MagicMock, PropertyMock


# ---------------------------------------------------------------------------
# Common mock objects — reusable across test modules
# ---------------------------------------------------------------------------


def make_mock_doc(doctype, **fields):
    """Create a MagicMock that behaves like a Frappe document.

    Usage:
        customer = make_mock_doc("Customer", customer_name="Acme Corp",
                                 whatsapp_number="+911234567890")
        assert customer.whatsapp_number == "+911234567890"
    """
    mock = MagicMock()
    mock.doctype = doctype
    mock.name = fields.get("name", f"NEW-{doctype}-001")
    for key, value in fields.items():
        setattr(mock, key, value)
    return mock


def make_mock_db_result(rows):
    """Create a mock for frappe.db.sql/as_dict results.

    Usage:
        data = make_mock_db_result([
            {"name": "INV-001", "outstanding_amount": 50000},
        ])
    """
    return rows


# ---------------------------------------------------------------------------
# Standard mock values for tests
# ---------------------------------------------------------------------------

MOCK_CUSTOMER = {
    "name": "_Test Customer",
    "customer_name": "Test Customer Pvt Ltd",
    "whatsapp_number": "+919999999999",
    "sms_number": "+919999999999",
    "preferred_language": "English",
    "preferred_channel": "WhatsApp",
    "custom_assigned_sales_rep": "Administrator",
    "owner": "Administrator",
}

MOCK_SALES_INVOICE = {
    "name": "SINV-00001",
    "customer": "_Test Customer",
    "due_date": "2026-07-01",
    "outstanding_amount": 50000.00,
    "company": "_Test Company",
    "docstatus": 1,
}

MOCK_DUNNING = {
    "name": "DUNN-00001",
    "customer": "_Test Customer",
    "sales_invoice": "SINV-00001",
    "escalation_stage": "Reminder 1",
    "dispute_flag": 0,
    "dispute_reason": "",
    "last_contact_channel": "",
    "promised_payment_date": None,
    "total_dunning": 50000.00,
}

MOCK_MESSAGE_TEMPLATE = {
    "template_name": "payment_due_reminder_en",
    "channel": "WhatsApp",
    "language": "English",
    "whatsapp_template_id": "payment_due_reminder_en",
    "body_text": (
        "Dear {customer_name}, your invoice {invoice_no} "
        "for ₹{amount} was due on {due_date} and is "
        "{days_overdue} days overdue. Please pay."
    ),
    "variables_order": (
        '["customer_name", "invoice_no", "amount", '
        '"due_date", "days_overdue"]'
    ),
}

MOCK_COMM_LOG = {
    "name": "COMMLOG-2026-07-20-00001",
    "dunning": "DUNN-00001",
    "customer": "_Test Customer",
    "channel": "WhatsApp",
    "message_template": "payment_due_reminder_en",
    "sent_on": "2026-07-20 10:00:00",
    "status": "Sent",
    "provider_message_id": "gupshup-msg-12345",
    "error_log": "",
}

MOCK_CADENCE_RULE = {
    "name": "CADENCE-0001",
    "days_overdue_from": 1,
    "days_overdue_to": 30,
    "action": "Send WhatsApp Reminder",
    "message_template": "payment_due_reminder_en",
    "active": 1,
}
