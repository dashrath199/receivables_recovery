# -*- coding: utf-8 -*-
"""Messaging module — real WhatsApp (Gupshup) and SMS (MSG91) integration.

API credentials are read from site_config.json (not hardcoded).

WhatsApp template approval note:
WhatsApp Business API requires all outbound business-initiated templates to be
pre-approved by Meta before they can be sent. The `whatsapp_template_id` field
in the Message Template DocType stores the approved template name/ID.

Until real approved template IDs are configured in the Message Template records,
`send_via_gupshup` calls will fail and log errors to Communication Log.error_log.
This is expected in a demo/development environment.
"""
from __future__ import unicode_literals
import frappe
import requests
import json
from frappe.utils import today, date_diff


@frappe.whitelist()
def send_payment_reminder(dunning_name, channel, message_template_name):
    """Send a payment reminder via the specified channel.

    Args:
        dunning_name: Name of the Dunning document
        channel: 'WhatsApp' or 'SMS'
        message_template_name: Name of the Message Template to use

    Returns:
        dict with status and provider_message_id if successful
    """
    dunning = frappe.get_doc("Dunning", dunning_name)
    customer = frappe.get_doc("Customer", dunning.customer)
    template = frappe.get_doc("Message Template", message_template_name)
    invoice = frappe.get_doc("Sales Invoice", dunning.sales_invoice)

    # Build the positional values array from the template's variables_order
    variables = json.loads(template.variables_order or "[]")
    values = build_template_values(customer, invoice, variables)

    # Create Communication Log entry (status: Queued)
    log = frappe.get_doc({
        "doctype": "Communication Log",
        "dunning": dunning_name,
        "customer": customer.name,
        "channel": channel,
        "message_template": message_template_name,
        "sent_on": frappe.utils.now(),
        "status": "Queued",
    })
    log.insert(ignore_permissions=True)

    try:
        if channel == "WhatsApp":
            response = send_via_gupshup(
                to_number=customer.whatsapp_number,
                template_id=template.whatsapp_template_id,
                values=values,
            )
        elif channel == "SMS":
            sms_number = customer.sms_number or customer.whatsapp_number
            response = send_via_msg91(
                to_number=sms_number,
                body_text=template.body_text,
                values=values,
            )
        else:
            raise ValueError(f"Unsupported channel: {channel}")

        # Extract provider message ID (Gupshup and MSG91 return different key names)
        provider_id = (
            response.get("messageId")
            or response.get("message_id")
            or response.get("request_id")
            or ""
        )

        # Update Communication Log
        frappe.db.set_value("Communication Log", log.name, {
            "status": "Sent",
            "provider_message_id": provider_id,
        })

        # Update Dunning's last contact channel
        frappe.db.set_value("Dunning", dunning_name, "last_contact_channel", channel)

        frappe.db.commit()

        return {
            "status": "Sent",
            "provider_message_id": provider_id,
            "communication_log": log.name,
        }

    except Exception as e:
        error_message = str(e)

        # Update Communication Log with failure
        frappe.db.set_value("Communication Log", log.name, {
            "status": "Failed",
            "error_log": error_message,
        })
        frappe.db.commit()

        # Log the error for monitoring
        frappe.log_error(
            f"Payment Reminder Send Failed\n"
            f"Dunning: {dunning_name}\n"
            f"Customer: {customer.name}\n"
            f"Channel: {channel}\n"
            f"Template: {message_template_name}\n"
            f"Error: {error_message}",
            "Receivables Recovery — Messaging",
        )

        return {
            "status": "Failed",
            "error": error_message,
            "communication_log": log.name,
        }


def build_template_values(customer, invoice, variables):
    """Build an ordered list of values matching the template's placeholder order.

    Maps variable names from variables_order to actual field values.

    Args:
        customer: Customer document
        invoice: Sales Invoice document
        variables: List of variable name strings from the template

    Returns:
        List of string values in the same order as the variables list
    """
    field_map = {
        "customer_name": customer.customer_name,
        "invoice_no": invoice.name,
        "amount": invoice.outstanding_amount,
        "outstanding_amount": invoice.outstanding_amount,
        "due_date": str(invoice.due_date),
        "days_overdue": date_diff(today(), invoice.due_date),
        "company": invoice.company,
    }
    return [str(field_map.get(v.strip(), "")) for v in variables]


def send_via_gupshup(to_number, template_id, values):
    """Send a WhatsApp message via Gupshup's Business API.

    https://docs.gupshup.io/docs/send-template-message

    Args:
        to_number: Recipient's WhatsApp number with country code (e.g., +919876543210)
        template_id: The approved WhatsApp template ID/name
        values: Ordered list of parameter values for the template placeholders

    Returns:
        Parsed JSON response from Gupshup API

    Raises:
        frappe.ValidationError: If API credentials are missing
        requests.RequestException: On API call failure
    """
    api_key = frappe.conf.get("gupshup_api_key")
    source = frappe.conf.get("gupshup_source_number")
    app_name = frappe.conf.get("gupshup_app_name")

    if not all([api_key, source, app_name]):
        raise frappe.ValidationError(
            "Gupshup API credentials not configured. "
            "Add gupshup_api_key, gupshup_source_number, and gupshup_app_name "
            "to site_config.json."
        )

    url = "https://api.gupshup.io/wa/api/v1/template/msg"
    headers = {
        "apikey": api_key,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "channel": "whatsapp",
        "source": source,
        "destination": to_number,
        "src.name": app_name,
        "template": json.dumps({"id": template_id, "params": values}),
    }

    resp = requests.post(url, headers=headers, data=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_via_msg91(to_number, body_text, values):
    """Send an SMS via MSG91's API.

    https://docs.msg91.com/

    Args:
        to_number: Recipient's phone number with country code
        body_text: Template body text with {} placeholders for positional replacement
        values: Ordered list of values to substitute into placeholders

    Returns:
        Parsed JSON response from MSG91 API

    Raises:
        frappe.ValidationError: If API credentials are missing
        requests.RequestException: On API call failure
    """
    auth_key = frappe.conf.get("msg91_auth_key")
    sender_id = frappe.conf.get("msg91_sender_id")

    if not all([auth_key, sender_id]):
        raise frappe.ValidationError(
            "MSG91 API credentials not configured. "
            "Add msg91_auth_key and msg91_sender_id to site_config.json."
        )

    # Simple positional replacement: each {} in body_text is replaced in order
    message = body_text
    for v in values:
        message = message.replace("{}", str(v), 1)

    url = "https://api.msg91.com/api/v5/flow/"
    headers = {
        "authkey": auth_key,
        "Content-Type": "application/json",
    }
    payload = {
        "sender": sender_id,
        "mobiles": to_number,
        "message": message,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()
