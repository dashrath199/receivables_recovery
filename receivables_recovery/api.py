# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _


# ---------------------------------------------------------------------------
# Webhook endpoints — registered in provider dashboards for delivery callbacks
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def gupshup_webhook():
    """Webhook endpoint for Gupshup delivery status callbacks.

    Register this URL in the Gupshup dashboard:
    https://yoursite.local/api/method/receivables_recovery.api.gupshup_webhook

    Expected payload format (Gupshup standard webhook):
    {
        "payload": {
            "id": "provider-message-id",
            "type": "sent" | "delivered" | "read" | "failed",
            "error": {...}   // optional, present on failure
        },
        "app": "app-name",
        "timestamp": 1234567890
    }
    """
    try:
        data = frappe.request.get_json()
    except Exception:
        frappe.response["http_status_code"] = 400
        return {"status": "error", "message": "Invalid JSON payload"}

    if not data:
        frappe.response["http_status_code"] = 400
        return {"status": "error", "message": "Empty payload"}

    payload = data.get("payload", {})
    message_id = payload.get("id")
    status_type = payload.get("type", "").lower()  # sent / delivered / read / failed

    if not message_id:
        frappe.response["http_status_code"] = 400
        return {"status": "error", "message": "Missing payload.id"}

    # Map Gupshup status types to Communication Log statuses
    status_map = {
        "sent": "Sent",
        "delivered": "Delivered",
        "read": "Read",
        "failed": "Failed",
        "enqueued": "Queued",
    }
    new_status = status_map.get(status_type, status_type.capitalize())

    # Find the Communication Log by provider_message_id
    log_name = frappe.db.get_value("Communication Log", {"provider_message_id": message_id}, "name")
    if log_name:
        frappe.db.set_value("Communication Log", log_name, "status", new_status)

        # If failed, capture error details
        if status_type == "failed":
            error_info = payload.get("error", {})
            error_details = str(error_info)
            frappe.db.set_value("Communication Log", log_name, "error_log", error_details)

        frappe.db.commit()

    return {"status": "ok", "message_id": message_id, "new_status": new_status}


@frappe.whitelist(allow_guest=True)
def msg91_webhook():
    """Webhook endpoint for MSG91 delivery reports.

    Register this URL in the MSG91 dashboard:
    https://yoursite.local/api/method/receivables_recovery.api.msg91_webhook

    Expected payload format (MSG91 DLT webhook):
    {
        "message_id": "provider-message-id",
        "status": "DELIVRD" | "UNDELIV" | ...,
        "error": "..."
    }
    """
    try:
        data = frappe.request.get_json()
    except Exception:
        frappe.response["http_status_code"] = 400
        return {"status": "error", "message": "Invalid JSON payload"}

    if not data:
        frappe.response["http_status_code"] = 400
        return {"status": "error", "message": "Empty payload"}

    message_id = data.get("message_id")
    status_code = data.get("status", "").upper()

    if not message_id:
        frappe.response["http_status_code"] = 400
        return {"status": "error", "message": "Missing message_id"}

    # Map MSG91 status codes to Communication Log statuses
    status_map = {
        "DELIVRD": "Delivered",
        "UNDELIV": "Failed",
        "EXPIRED": "Failed",
        "DELETED": "Failed",
        "UNDELIVERABLE": "Failed",
        "REJECTED": "Failed",
        "SENT": "Sent",
        "SENDING": "Queued",
        "READ": "Read",
    }
    new_status = status_map.get(status_code, "Sent")

    log_name = frappe.db.get_value("Communication Log", {"provider_message_id": message_id}, "name")
    if log_name:
        frappe.db.set_value("Communication Log", log_name, "status", new_status)

        if new_status == "Failed":
            error_details = data.get("error", str(data))
            frappe.db.set_value("Communication Log", log_name, "error_log", error_details)

        frappe.db.commit()

    return {"status": "ok", "message_id": message_id, "new_status": new_status}


# ---------------------------------------------------------------------------
# Permission query conditions — role-based access control for Dunning
# ---------------------------------------------------------------------------


def get_permission_query_conditions_for_dunning(user):
    """Restrict Dunning access for Sales Reps to their own customers only.

    Collections Managers and System Managers see all records.
    """
    if not user:
        user = frappe.session.user

    user_roles = frappe.get_roles(user)

    if "System Manager" in user_roles or "Collections Manager" in user_roles:
        return ""  # No restriction

    if "Sales Rep" in user_roles:
        # Sales Reps can only see Dunning records for their assigned customers
        return (
            "(`tabDunning`.`customer` IN ("
            "   SELECT `tabCustomer`.`name`"
            "   FROM `tabCustomer`"
            "   WHERE `tabCustomer`.`custom_assigned_sales_rep` = %(user)s"
            "   OR `tabCustomer`.`owner` = %(user)s"
            "))"
        )

    # Default: show nothing if no relevant role
    return "1=0"


def has_dunning_permission(doc, ptype, user):
    """Check if user has permission for a specific Dunning document.

    Sales Reps can only read/update Dunning records for their assigned customers.
    They can update last_contact_channel and promised_payment_date, but not
    escalation_stage (legal escalation requires manager sign-off).
    """
    user_roles = frappe.get_roles(user)

    if "System Manager" in user_roles or "Collections Manager" in user_roles:
        return True

    if "Sales Rep" in user_roles:
        # Check if this Sales Rep is assigned to the customer
        customer = frappe.get_doc("Customer", doc.customer)
        assigned_rep = getattr(customer, "custom_assigned_sales_rep", None)
        if assigned_rep == user or customer.owner == user:
            return True

    return False


# ---------------------------------------------------------------------------
# Document validation hooks
# ---------------------------------------------------------------------------


def validate_dunning(doc, method):
    """Validate Dunning document before save.

    - If dispute_flag is set, require dispute_reason
    - If escalation_stage changes, log the change
    - Prevent Sales Reps from changing escalation_stage
    """
    user = frappe.session.user
    user_roles = frappe.get_roles(user)

    # Require dispute_reason when dispute_flag is checked
    if doc.dispute_flag and not doc.dispute_reason:
        frappe.throw(_("Dispute Reason is required when Dispute Flag is checked."))

    # Check if escalation_stage is being changed by a non-manager
    if doc.get_doc_before_save():
        old_stage = doc.get_doc_before_save().get("escalation_stage")
        if old_stage and old_stage != doc.escalation_stage:
            if "Sales Rep" in user_roles and "Collections Manager" not in user_roles:
                frappe.throw(
                    _("Sales Reps cannot change the Escalation Stage. "
                      "Please contact a Collections Manager.")
                )

            # Log escalation stage changes for audit
            frappe.log_error(
                f"Dunning {doc.name}: Escalation stage changed from "
                f"'{old_stage}' to '{doc.escalation_stage}' by {user}",
                "Collections Escalation Audit",
            )
