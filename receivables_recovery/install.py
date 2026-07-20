# -*- coding: utf-8 -*-
"""Installation script — seeds demo data for immediate demoability.

All demo data uses placeholder/test contact numbers and WhatsApp template IDs.
Real WhatsApp templates must be created and approved in the Gupshup/Meta Business
dashboard before live sending will work.
"""
from __future__ import unicode_literals
import frappe
from frappe.utils import add_days, today, now_datetime


def after_install():
    """Run after the app is installed.

    1. Import fixtures (custom fields, roles, workspace, notifications)
    2. Seed demo data
    """
    if frappe.db.exists("Message Template", "payment_due_reminder_en"):
        return  # Already seeded

    import_fixtures()
    create_demo_customers()
    create_demo_templates()       # Must come before cadence rules (rules link to templates)
    create_demo_cadence_rules()
    create_demo_invoices()
    create_demo_dunning_and_logs()

    frappe.db.commit()


def before_uninstall():
    """Clean up demo data before uninstalling (optional safety)."""
    pass


# ---------------------------------------------------------------------------
# Fixture import — ensures custom fields, roles, workspace, and notifications
# are created when the app is installed, not just on bench import-fixtures
# ---------------------------------------------------------------------------


def import_fixtures():
    """Import all fixtures from the fixtures/ and other JSON files."""
    import_custom_fields()
    import_roles()
    import_notifications()
    import_workspace()


def import_custom_fields():
    """Import custom fields from fixtures/custom_fields.json."""
    import_json_fixture("receivables_recovery/fixtures/custom_fields.json", "Custom Field")


def import_roles():
    """Import roles from fixtures/roles.json."""
    import_json_fixture("receivables_recovery/fixtures/roles.json", "Role")


def import_notifications():
    """Import notification definitions."""
    notifications_dir = frappe.get_app_path("receivables_recovery", "notification")
    import_json_directory_fixtures(notifications_dir, "Notification")


def import_workspace():
    """Import workspace definition."""
    workspace_path = frappe.get_app_path(
        "receivables_recovery",
        "workspace",
        "receivables_and_collections",
        "receivables_and_collections.json",
    )
    if frappe.get_file_json(workspace_path):
        import_single_fixture(workspace_path, "Workspace")


def import_json_fixture(filepath_rel, doctype):
    """Import a JSON fixture file into a Frappe DocType.

    Args:
        filepath_rel: Path relative to the app, e.g. "receivables_recovery/fixtures/custom_fields.json"
        doctype: Target DocType name, e.g. "Custom Field"
    """
    try:
        filepath = frappe.get_app_path(filepath_rel)
        records = frappe.get_file_json(filepath)
        if not records:
            return

        for record in records:
            if frappe.db.exists(doctype, record.get("name") or record.get("fieldname")):
                continue
            try:
                doc = frappe.get_doc(record)
                doc.flags.ignore_permissions = True
                doc.flags.ignore_mandatory = True
                doc.insert(ignore_permissions=True, ignore_mandatory=True)
            except Exception as e:
                frappe.log_error(
                    f"Failed to import {doctype} fixture {record.get('name', '')}: {str(e)}",
                    "Receivables Recovery — Fixture Import",
                )
    except Exception as e:
        frappe.log_error(
            f"Failed to import fixture file {filepath_rel}: {str(e)}",
            "Receivables Recovery — Fixture Import",
        )


def import_json_directory_fixtures(directory, doctype):
    """Import all JSON fixture files in a directory hierarchy."""
    import os
    import glob

    pattern = os.path.join(directory, "**", "*.json")
    for filepath in glob.glob(pattern, recursive=True):
        import_single_fixture(filepath, doctype)


def import_single_fixture(filepath, doctype):
    """Import a single JSON fixture file."""
    try:
        record = frappe.get_file_json(filepath)
        if not record:
            return

        if isinstance(record, list):
            for r in record:
                insert_fixture_record(r, doctype)
        else:
            insert_fixture_record(record, doctype)
    except Exception as e:
        frappe.log_error(
            f"Failed to import fixture from {filepath}: {str(e)}",
            "Receivables Recovery — Fixture Import",
        )


def insert_fixture_record(record, doctype):
    """Insert a single fixture record if it doesn't already exist."""
    name_key = record.get("name") or record.get("fieldname") or record.get("template_name")
    if name_key and frappe.db.exists(doctype, name_key):
        return

    try:
        doc = frappe.get_doc({"doctype": doctype, **record})
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
    except Exception as e:
        frappe.log_error(
            f"Failed to insert {doctype} record: {str(e)}",
            "Receivables Recovery — Fixture Import",
        )


# ---------------------------------------------------------------------------
# Demo Customers
# ---------------------------------------------------------------------------


def create_demo_customers():
    customers = [
        {
            "customer_name": "Acme Corp Pvt Ltd",
            "customer_type": "Company",
            "whatsapp_number": "+919876543201",
            "sms_number": "+919876543201",
            "preferred_language": "English",
            "preferred_channel": "WhatsApp",
        },
        {
            "customer_name": "Bharat Electronics",
            "customer_type": "Company",
            "whatsapp_number": "+919876543202",
            "sms_number": "+919876543202",
            "preferred_language": "Hindi",
            "preferred_channel": "SMS",
        },
        {
            "customer_name": "Coastal Traders",
            "customer_type": "Individual",
            "whatsapp_number": "+919876543203",
            "sms_number": "",
            "preferred_language": "Kannada",
            "preferred_channel": "WhatsApp",
        },
        {
            "customer_name": "Delta Manufacturing Co",
            "customer_type": "Company",
            "whatsapp_number": "+919876543204",
            "sms_number": "+919876543204",
            "preferred_language": "English",
            "preferred_channel": "Email",
        },
        {
            "customer_name": "Epsilon Retail Solutions",
            "customer_type": "Company",
            "whatsapp_number": "+919876543205",
            "sms_number": "+919876543205",
            "preferred_language": "Tamil",
            "preferred_channel": "WhatsApp",
        },
    ]

    for c in customers:
        if not frappe.db.exists("Customer", c["customer_name"]):
            doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": c["customer_name"],
                "customer_type": c["customer_type"],
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
                "whatsapp_number": c["whatsapp_number"],
                "sms_number": c["sms_number"] or c["whatsapp_number"],
                "preferred_language": c["preferred_language"],
                "preferred_channel": c["preferred_channel"],
                "custom_assigned_sales_rep": "Administrator",
            })
            doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Demo Collections Cadence Rules
# ---------------------------------------------------------------------------


def create_demo_cadence_rules():
    rules = [
        {
            "days_overdue_from": 1,
            "days_overdue_to": 30,
            "action": "Send WhatsApp Reminder",
            "message_template": "payment_due_reminder_en",
        },
        {
            "days_overdue_from": 31,
            "days_overdue_to": 60,
            "action": "Send SMS",
            "message_template": "payment_due_reminder_hi",
        },
        {
            "days_overdue_from": 61,
            "days_overdue_to": 90,
            "action": "Flag for Call",
            "message_template": "",
        },
        {
            "days_overdue_from": 91,
            "days_overdue_to": 9999,
            "action": "Escalate to Legal",
            "message_template": "",
        },
    ]

    for r in rules:
        if not frappe.db.exists("Collections Cadence Rule", {"action": r["action"], "days_overdue_from": r["days_overdue_from"]}):
            doc = frappe.get_doc({
                "doctype": "Collections Cadence Rule",
                "days_overdue_from": r["days_overdue_from"],
                "days_overdue_to": r["days_overdue_to"],
                "action": r["action"],
                "message_template": r.get("message_template", ""),
                "active": 1,
            })
            doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Demo Message Templates
# ---------------------------------------------------------------------------


def create_demo_templates():
    templates = [
        {
            "template_name": "payment_due_reminder_en",
            "channel": "WhatsApp",
            "language": "English",
            "whatsapp_template_id": "payment_due_reminder_en",
            # ⚠ PLACEHOLDER — Replace with real approved template ID before going live
            "body_text": "Dear {customer_name}, your invoice {invoice_no} for ₹{amount} was due on {due_date} and is {days_overdue} days overdue. Please pay at your earliest convenience to avoid escalation.",
            "variables_order": '["customer_name", "invoice_no", "amount", "due_date", "days_overdue"]',
        },
        {
            "template_name": "payment_due_reminder_hi",
            "channel": "SMS",
            "language": "Hindi",
            "whatsapp_template_id": "",
            "body_text": "प्रिय {customer_name}, आपका चालान {invoice_no} ({amount} रुपये) की नियत तिथि {due_date} थी और यह {days_overdue} दिनों से अतिदेय है। कृपया शीघ्र भुगतान करें।",
            "variables_order": '["customer_name", "invoice_no", "amount", "due_date", "days_overdue"]',
        },
        {
            "template_name": "final_notice_en",
            "channel": "WhatsApp",
            "language": "English",
            "whatsapp_template_id": "final_notice_en",
            # ⚠ PLACEHOLDER — Replace with real approved template ID before going live
            "body_text": "FINAL NOTICE: Dear {customer_name}, invoice {invoice_no} for ₹{amount} is now {days_overdue} days overdue. Immediate payment is required to avoid legal escalation.",
            "variables_order": '["customer_name", "invoice_no", "amount", "days_overdue"]',
        },
    ]

    for t in templates:
        if not frappe.db.exists("Message Template", t["template_name"]):
            doc = frappe.get_doc({
                "doctype": "Message Template",
                "template_name": t["template_name"],
                "channel": t["channel"],
                "language": t["language"],
                "whatsapp_template_id": t["whatsapp_template_id"],
                "body_text": t["body_text"],
                "variables_order": t["variables_order"],
            })
            doc.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Demo Sales Invoices (overdue, spread across aging buckets)
# ---------------------------------------------------------------------------


def create_demo_invoices():
    invoices_data = [
        # 5 days overdue — Reminder 1 bucket
        {"customer": "Acme Corp Pvt Ltd", "days_overdue": 5, "amount": 45000},
        {"customer": "Acme Corp Pvt Ltd", "days_overdue": 8, "amount": 28000},

        # 45 days overdue — Reminder 2 bucket
        {"customer": "Bharat Electronics", "days_overdue": 45, "amount": 123000},
        {"customer": "Bharat Electronics", "days_overdue": 50, "amount": 87500},

        # 75 days overdue — Final Notice bucket
        {"customer": "Coastal Traders", "days_overdue": 75, "amount": 67000},
        {"customer": "Coastal Traders", "days_overdue": 80, "amount": 34000},

        # 120+ days overdue — Legal Referral bucket
        {"customer": "Delta Manufacturing Co", "days_overdue": 120, "amount": 250000},
        {"customer": "Delta Manufacturing Co", "days_overdue": 150, "amount": 185000},

        # Mixed for Epsilon
        {"customer": "Epsilon Retail Solutions", "days_overdue": 15, "amount": 32000},
        {"customer": "Epsilon Retail Solutions", "days_overdue": 65, "amount": 56000},
        {"customer": "Epsilon Retail Solutions", "days_overdue": 95, "amount": 78000},

        # Extra for Acme
        {"customer": "Acme Corp Pvt Ltd", "days_overdue": 110, "amount": 92000},

        # Extra for Bharat
        {"customer": "Bharat Electronics", "days_overdue": 20, "amount": 45000},

        # Extra for Coastal
        {"customer": "Coastal Traders", "days_overdue": 3, "amount": 15000},

        # Extra for Delta
        {"customer": "Delta Manufacturing Co", "days_overdue": 35, "amount": 98000},
    ]

    # Get company name from system (default if not set)
    company = frappe.db.get_single_value("Global Defaults", "default_company") or "Acme Corp Pvt Ltd"

    # Get default income account
    income_account = frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Income", "is_group": 0},
        "name",
    ) or frappe.db.get_value("Account", {"company": company, "account_type": "Income"}, "name")

    # Get default cost center
    cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
    if not cost_center:
        cost_center = frappe.db.get_value("Cost Center", {"company": company}, "name")

    item_name = "Consulting Services"

    for idx, inv_data in enumerate(invoices_data):
        customer = inv_data["customer"]
        due_date = add_days(today(), -inv_data["days_overdue"])
        posting_date = add_days(due_date, -5)  # Invoice posted 5 days before due
        amount = inv_data["amount"]

        invoice_name = f"DEMO-ACC-{idx + 1:04d}"

        if frappe.db.exists("Sales Invoice", invoice_name):
            continue

        try:
            doc = frappe.get_doc({
                "doctype": "Sales Invoice",
                "title": invoice_name,
                "customer": customer,
                "company": company,
                "posting_date": posting_date,
                "due_date": due_date,
                "items": [
                    {
                        "item_name": item_name,
                        "description": f"Professional services — Invoice {idx + 1}",
                        "qty": 1,
                        "rate": amount,
                        "income_account": income_account,
                        "cost_center": cost_center,
                    }
                ],
                # Set outstanding amount directly (bypass payment requirements)
                "outstanding_amount": amount,
                "status": "Overdue",
            })
            doc.flags.ignore_mandatory = True
            doc.flags.ignore_permissions = True
            doc.insert(ignore_permissions=True, ignore_mandatory=True)

            # Ensure it's submitted
            if doc.docstatus == 0:
                doc.submit()

        except Exception as e:
            frappe.log_error(f"Failed to create demo invoice {invoice_name}: {str(e)}", "Receivables Recovery Demo")


# ---------------------------------------------------------------------------
# Demo Dunning Records & Communication Logs
# ---------------------------------------------------------------------------


def create_demo_dunning_and_logs():
    """Create pre-populated Dunning records and Communication Log entries."""

    # Get the Sales Invoices we just created
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"title": ["like", "DEMO-ACC-%"]},
        fields=["name", "customer", "due_date", "outstanding_amount"],
    )

    # 1. Dunning at Reminder 1 stage (Acme — 5 days overdue)
    inv_5d = next((i for i in invoices if i.get("due_date") == add_days(today(), -5)), None)
    if inv_5d:
        dunning = create_dunning(
            inv_5d.customer,
            inv_5d.name,
            "Reminder 1",
            dispute_flag=0,
            last_contact="WhatsApp",
            promised_date=None,
        )
        if dunning:
            create_comm_log(dunning.name, inv_5d.customer, "WhatsApp", "Sent", "payment_due_reminder_en")

    # 2. Dunning at Reminder 2 stage (Bharat — 50 days overdue)
    inv_50d = next((i for i in invoices if i.get("due_date") == add_days(today(), -50)), None)
    if inv_50d:
        dunning = create_dunning(
            inv_50d.customer,
            inv_50d.name,
            "Reminder 2",
            dispute_flag=0,
            last_contact="SMS",
            promised_date=None,
        )
        if dunning:
            create_comm_log(dunning.name, inv_50d.customer, "SMS", "Delivered", "payment_due_reminder_hi")

    # 3. Dunning with dispute_flag = 1 (Coastal — 80 days overdue)
    inv_80d = next((i for i in invoices if i.get("due_date") == add_days(today(), -80)), None)
    if inv_80d:
        create_dunning(
            inv_80d.customer,
            inv_80d.name,
            "Final Notice",
            dispute_flag=1,
            dispute_reason="Customer claims the service was not delivered as per the contract terms. Received legal notice from their counsel on 2026-07-01.",
            last_contact="Call",
            promised_date=None,
        )

    # 4. Dunning with broken promise (Delta — 150 days overdue)
    inv_150d = next((i for i in invoices if i.get("due_date") == add_days(today(), -150)), None)
    if inv_150d:
        dunning = create_dunning(
            inv_150d.customer,
            inv_150d.name,
            "Legal Referral",
            dispute_flag=0,
            last_contact="Call",
            promised_date=add_days(today(), -10),  # Past — broken promise
        )
        if dunning:
            create_comm_log(dunning.name, inv_150d.customer, "WhatsApp", "Delivered", "final_notice_en")
            create_comm_log(dunning.name, inv_150d.customer, "Call", "Sent", None)

    # 5. Dunning with communication log failure example (Epsilon — 95 days overdue)
    inv_95d = next((i for i in invoices if i.get("due_date") == add_days(today(), -95)), None)
    if inv_95d:
        dunning = create_dunning(
            inv_95d.customer,
            inv_95d.name,
            "Final Notice",
            dispute_flag=0,
            last_contact="WhatsApp",
            promised_date=None,
        )
        if dunning:
            create_comm_log(
                dunning.name, inv_95d.customer, "WhatsApp", "Failed",
                "final_notice_en",
                error_log="HTTP 401: Unauthorized — Invalid Gupshup API key (simulated demo error)",
            )

    # 6. Dunning at Reminder 1 (Epsilon — 15 days overdue) with mixed status logs
    inv_15d = next((i for i in invoices if i.get("due_date") == add_days(today(), -15)), None)
    if inv_15d:
        dunning = create_dunning(
            inv_15d.customer,
            inv_15d.name,
            "Reminder 1",
            dispute_flag=0,
            last_contact="WhatsApp",
            promised_date=None,
        )
        if dunning:
            create_comm_log(dunning.name, inv_15d.customer, "WhatsApp", "Sent", "payment_due_reminder_en")
            create_comm_log(dunning.name, inv_15d.customer, "WhatsApp", "Delivered", None)
            create_comm_log(dunning.name, inv_15d.customer, "WhatsApp", "Read", None)


def create_dunning(customer, invoice, stage, dispute_flag=0, dispute_reason="", last_contact="", promised_date=None):
    """Helper to create a Dunning record for demo purposes."""
    existing = frappe.db.get_value("Dunning", {"sales_invoice": invoice}, "name")
    if existing:
        return frappe.get_doc("Dunning", existing)

    try:
        doc = frappe.get_doc({
            "doctype": "Dunning",
            "customer": customer,
            "sales_invoice": invoice,
            "escalation_stage": stage,
            "dispute_flag": dispute_flag,
            "dispute_reason": dispute_reason,
            "last_contact_channel": last_contact,
            "promised_payment_date": promised_date,
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)
        return doc
    except Exception as e:
        frappe.log_error(f"Failed to create demo Dunning for {invoice}: {str(e)}", "Receivables Recovery Demo")
        return None


def create_comm_log(dunning_name, customer, channel, status, message_template=None, error_log=""):
    """Helper to create a Communication Log entry for demo purposes."""
    try:
        doc = frappe.get_doc({
            "doctype": "Communication Log",
            "dunning": dunning_name,
            "customer": customer,
            "channel": channel,
            "message_template": message_template or "",
            "sent_on": now_datetime(),
            "status": status,
            "error_log": error_log,
            "provider_message_id": f"demo-{frappe.generate_hash(length=12)}",
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)
        return doc
    except Exception as e:
        frappe.log_error(f"Failed to create demo Communication Log: {str(e)}", "Receivables Recovery Demo")
        return None
