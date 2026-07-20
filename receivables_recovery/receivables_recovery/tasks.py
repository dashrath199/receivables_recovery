# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import today, date_diff, now_datetime, add_to_date


def run_collections_cadence():
    """Main scheduled job — runs daily to evaluate overdue invoices against cadence rules.

    For each overdue invoice:
    1. Find the matching Collections Cadence Rule based on days overdue
    2. Get or create the corresponding Dunning record
    3. Skip if already contacted today or invoice is disputed
    4. Execute the rule's action (send message, flag for call, or escalate)
    """
    overdue_invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "outstanding_amount": [">", 0],
            "due_date": ["<", today()],
            "docstatus": 1,
        },
        fields=["name", "customer", "due_date", "outstanding_amount"],
    )

    if not overdue_invoices:
        frappe.log_error("No overdue invoices found for collections cadence.", "Receivables Recovery")
        return

    for inv in overdue_invoices:
        days_overdue = date_diff(today(), inv.due_date)

        rule = frappe.db.get_value(
            "Collections Cadence Rule",
            {
                "days_overdue_from": ["<=", days_overdue],
                "days_overdue_to": [">=", days_overdue],
                "active": 1,
            },
            ["name", "action", "message_template"],
            as_dict=True,
        )
        if not rule:
            continue

        dunning = get_or_create_dunning(inv, days_overdue)

        # Skip if already contacted today for this dunning
        if already_sent_today(dunning.name):
            continue

        # Never auto-message disputed invoices
        if dunning.dispute_flag:
            continue

        # Execute the rule action
        if rule.action == "Send WhatsApp Reminder":
            send_payment_reminder(dunning.name, "WhatsApp", rule.message_template)
        elif rule.action == "Send SMS":
            send_payment_reminder(dunning.name, "SMS", rule.message_template)
        elif rule.action == "Flag for Call":
            flag_for_call(dunning.name)
        elif rule.action == "Escalate to Legal":
            escalate_to_legal(dunning.name)


def get_or_create_dunning(invoice, days_overdue):
    """Get existing Dunning for this invoice or create a new one."""
    existing = frappe.db.get_value("Dunning", {"sales_invoice": invoice.name}, "name")
    if existing:
        dunning = frappe.get_doc("Dunning", existing)
        # Update escalation stage if needed
        new_stage = get_escalation_stage_for_days(days_overdue)
        if new_stage and dunning.escalation_stage != new_stage:
            dunning.db_set("escalation_stage", new_stage)
        return dunning

    doc = frappe.get_doc({
        "doctype": "Dunning",
        "customer": invoice.customer,
        "sales_invoice": invoice.name,
        "escalation_stage": get_escalation_stage_for_days(days_overdue) or "Reminder 1",
    })
    doc.insert(ignore_permissions=True)
    return doc


def get_escalation_stage_for_days(days_overdue):
    """Map days overdue to escalation stage."""
    if days_overdue <= 30:
        return "Reminder 1"
    elif days_overdue <= 60:
        return "Reminder 2"
    elif days_overdue <= 90:
        return "Final Notice"
    else:
        return "Legal Referral"


def already_sent_today(dunning_name):
    """Check if any communication was sent for this dunning today."""
    return frappe.db.exists("Communication Log", {
        "dunning": dunning_name,
        "sent_on": [">=", today()],
    })


def send_payment_reminder(dunning_name, channel, message_template_name):
    """Delegate sending to the messaging module."""
    from receivables_recovery.messaging import send_payment_reminder as _send

    _send(dunning_name, channel, message_template_name)


def flag_for_call(dunning_name):
    """Flag dunning for a personal call — creates a ToDo for the assigned Sales Rep."""
    dunning = frappe.get_doc("Dunning", dunning_name)
    dunning.db_set("last_contact_channel", "Call")

    # Find the Sales Rep/User assigned to this customer
    customer = frappe.get_doc("Customer", dunning.customer)
    assigned_user = customer.custom_assigned_sales_rep or customer.owner

    todo = frappe.get_doc({
        "doctype": "ToDo",
        "reference_type": "Dunning",
        "reference_name": dunning_name,
        "description": (
            f"Overdue invoice {dunning.sales_invoice} for {dunning.customer} "
            f"(outstanding: {dunning.total_dunning or 'see invoice'}) "
            f"requires a personal call — do not auto-message."
        ),
        "assigned_by": "Administrator",
        "owner": assigned_user,
        "priority": "Medium",
        "status": "Open",
    })
    todo.insert(ignore_permissions=True)

    frappe.msgprint(f"ToDo created: Flag for Call — {dunning_name}", alert=True)


def escalate_to_legal(dunning_name):
    """Escalate dunning to legal — manual-review gate, sends internal email only."""
    dunning = frappe.get_doc("Dunning", dunning_name)
    dunning.db_set("escalation_stage", "Legal Referral")

    # The actual email alert is handled by the Notification (see notification/ directory).
    # Log the escalation for audit trail.
    frappe.log_error(
        f"Dunning {dunning_name} escalated to Legal Referral. "
        f"Customer: {dunning.customer}, Invoice: {dunning.sales_invoice}",
        "Collections Escalation",
    )


def check_broken_promises():
    """Daily check for promises-to-pay that have passed without payment.

    A promise is considered "broken" when:
    - promised_payment_date < today AND
    - No matching Payment Entry exists for the Sales Invoice
    - Dunning is not already in Legal Referral stage
    """
    today_date = today()
    broken_promises = frappe.db.sql("""
        SELECT
            d.name AS dunning_name,
            d.customer,
            d.sales_invoice,
            d.promised_payment_date,
            d.escalation_stage
        FROM `tabDunning` d
        WHERE
            d.promised_payment_date IS NOT NULL
            AND d.promised_payment_date < %(today)s
            AND d.escalation_stage != 'Legal Referral'
            AND NOT EXISTS (
                SELECT 1 FROM `tabPayment Entry Reference` per
                INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
                WHERE per.reference_name = d.sales_invoice
                AND pe.docstatus = 1
            )
    """, {"today": today_date}, as_dict=True)

    for bp in broken_promises:
        # Update stage
        frappe.db.set_value("Dunning", bp.dunning_name, "escalation_stage", "Final Notice")

        # Create a notification log for the Collections Manager
        try:
            notification = frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Promise Broken: {bp.customer} — {bp.sales_invoice}",
                "email_content": (
                    f"Customer: {bp.customer}<br>"
                    f"Invoice: {bp.sales_invoice}<br>"
                    f"Promised Payment Date: {bp.promised_payment_date}<br>"
                    f"Action Required: Flag for a personal call — do not auto-send another templated reminder."
                ),
                "document_type": "Dunning",
                "document_name": bp.dunning_name,
                "for_user": "Administrator",
            })
            notification.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(f"Failed to create broken promise notification for {bp.dunning_name}", "Receivables Recovery")


def retry_failed_messages():
    """Hourly job to retry sending failed messages that have retry count < 3."""
    failed_logs = frappe.get_all(
        "Communication Log",
        filters={
            "status": "Failed",
            "sent_on": [">=", add_to_date(now_datetime(), hours=-24, as_string=True)],
        },
        fields=["name", "dunning", "channel", "message_template"],
    )

    for log in failed_logs:
        try:
            dunning = frappe.get_doc("Dunning", log.dunning)
            if dunning.dispute_flag:
                continue

            send_payment_reminder(log.dunning, log.channel, log.message_template)
            frappe.db.set_value("Communication Log", log.name, "status", "Queued")
        except Exception:
            frappe.log_error(f"Retry failed for Communication Log {log.name}", "Receivables Recovery")
