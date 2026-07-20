# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json


class MessageTemplate(Document):
    """Multi-language, multi-channel message template for collections communications.

    Each template can serve WhatsApp, SMS, or Email and supports
    placeholders for dynamic values like {customer_name}, {amount}, etc.
    The `whatsapp_template_id` field holds the pre-approved template ID
    from the WhatsApp Business API provider (Gupshup/Meta).
    """

    def validate(self):
        self.validate_variables_order()
        self.validate_whatsapp_template()

    def validate_variables_order(self):
        """Validate that variables_order is valid JSON list if provided."""
        if self.variables_order:
            try:
                parsed = json.loads(self.variables_order)
                if not isinstance(parsed, list):
                    frappe.throw("Variables Order must be a JSON array, e.g. [\"customer_name\", \"amount\"]")
            except json.JSONDecodeError:
                frappe.throw("Variables Order contains invalid JSON. Provide a valid JSON array.")

    def validate_whatsapp_template(self):
        """For WhatsApp templates, require the template ID."""
        if self.channel == "WhatsApp" and not self.whatsapp_template_id:
            frappe.throw(
                "WhatsApp Template ID is required for WhatsApp templates. "
                "Create and approve the template in your Gupshup/Meta Business dashboard first."
            )
