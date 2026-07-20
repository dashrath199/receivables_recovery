# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


class CommunicationLog(Document):
    """Tracks every outbound message sent through the collections cadence.

    Records channel, provider message ID, and delivery status.
    Status is updated via provider webhooks (Gupshup/MSG91) to track
    the full lifecycle: Queued → Sent → Delivered → Read (or Failed).
    """

    def validate(self):
        self.validate_sent_on()

    def validate_sent_on(self):
        if not self.sent_on:
            self.sent_on = frappe.utils.now()

    def on_update(self):
        """Trigger notification if status changes to Failed."""
        if self.status == "Failed" and self.error_log:
            self._notify_failure()

    def _notify_failure(self):
        """Create a system notification for failed message delivery."""
        try:
            from frappe.utils import get_url

            notification = frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Message Delivery Failed: {self.name}",
                "email_content": (
                    f"Communication Log: {self.name}<br>"
                    f"Customer: {self.customer}<br>"
                    f"Channel: {self.channel}<br>"
                    f"Error: {self.error_log}<br>"
                    f"Link: {get_url()}/app/communication-log/{self.name}"
                ),
                "document_type": "Communication Log",
                "document_name": self.name,
                "for_user": "Administrator",
            })
            notification.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error("Failed to create notification for message delivery failure", "Communication Log")
