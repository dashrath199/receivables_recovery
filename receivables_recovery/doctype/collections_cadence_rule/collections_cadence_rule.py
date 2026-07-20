# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


class CollectionsCadenceRule(Document):
    """Defines what action to take based on how many days an invoice is overdue.

    Actions include:
    - Send WhatsApp Reminder (requires message_template with WhatsApp channel)
    - Send SMS (requires message_template with SMS channel)
    - Flag for Call (creates a ToDo for the Sales Rep)
    - Escalate to Legal (sets escalation_stage and triggers notification)
    """

    def validate(self):
        self.validate_date_ranges()
        self.validate_message_template_for_action()

    def validate_date_ranges(self):
        """Ensure days_overdue_from <= days_overdue_to and ranges don't overlap."""
        if self.days_overdue_from > self.days_overdue_to:
            frappe.throw("Days Overdue From must be less than or equal to Days Overdue To.")

        # Check for overlapping active rules
        overlapping = frappe.db.exists(
            "Collections Cadence Rule",
            {
                "days_overdue_from": ["<=", self.days_overdue_to],
                "days_overdue_to": [">=", self.days_overdue_from],
                "active": 1,
                "name": ["!=", self.name or "New"],
            },
        )
        if overlapping:
            frappe.msgprint(
                "Warning: This rule's date range overlaps with another active rule. "
                "Only the first matching rule will be applied.",
                alert=True,
                indicator="orange",
            )

    def validate_message_template_for_action(self):
        """Require message_template for WhatsApp/SMS actions."""
        if self.action in ("Send WhatsApp Reminder", "Send SMS") and not self.message_template:
            frappe.throw(
                f"Message Template is required for action '{self.action}'. "
                "Please select a template."
            )
