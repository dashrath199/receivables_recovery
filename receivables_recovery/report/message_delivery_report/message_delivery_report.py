# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    """Message Delivery Report.

    Shows Sent/Delivered/Read/Failed counts by channel (WhatsApp, SMS, Email, Call).
    Includes a donut chart for visual breakdown and summary stats.
    """
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)

    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Channel"), "fieldname": "channel", "fieldtype": "Data", "width": 120},
        {"label": _("Total"), "fieldname": "total", "fieldtype": "Int", "width": 100},
        {"label": _("Queued"), "fieldname": "queued", "fieldtype": "Int", "width": 100},
        {"label": _("Sent"), "fieldname": "sent", "fieldtype": "Int", "width": 100},
        {"label": _("Delivered"), "fieldname": "delivered", "fieldtype": "Int", "width": 100},
        {"label": _("Read"), "fieldname": "read", "fieldtype": "Int", "width": 100},
        {"label": _("Failed"), "fieldname": "failed", "fieldtype": "Int", "width": 100},
        {"label": _("Delivery Rate (%)"), "fieldname": "delivery_rate", "fieldtype": "Percent", "width": 130},
    ]


def get_data(filters=None):
    """Fetch Communication Log entries grouped by channel with status counts."""
    conditions = ""
    if filters and filters.get("from_date"):
        conditions += f" AND cl.sent_on >= {frappe.db.escape(filters['from_date'])}"
    if filters and filters.get("to_date"):
        conditions += f" AND cl.sent_on <= {frappe.db.escape(filters['to_date'])}"
    if filters and filters.get("channel"):
        conditions += f" AND cl.channel = {frappe.db.escape(filters['channel'])}"

    data = frappe.db.sql(f"""
        SELECT
            cl.channel,
            COUNT(cl.name) AS total,
            SUM(CASE WHEN cl.status = 'Queued' THEN 1 ELSE 0 END) AS queued,
            SUM(CASE WHEN cl.status = 'Sent' THEN 1 ELSE 0 END) AS sent,
            SUM(CASE WHEN cl.status = 'Delivered' THEN 1 ELSE 0 END) AS delivered,
            SUM(CASE WHEN cl.status = 'Read' THEN 1 ELSE 0 END) AS `read`,
            SUM(CASE WHEN cl.status = 'Failed' THEN 1 ELSE 0 END) AS failed
        FROM `tabCommunication Log` cl
        WHERE 1=1
            {conditions}
        GROUP BY cl.channel
        ORDER BY cl.channel
    """, as_dict=1)

    for row in data:
        successful = row.get("delivered", 0) + row.get("read", 0)
        row.delivery_rate = round((successful / row.total) * 100, 1) if row.total > 0 else 0

    return data


def get_chart(data):
    """Return donut chart — delivery status breakdown."""
    if not data:
        return None

    # Aggregate all statuses across channels for the donut
    total_queued = sum(d.get("queued", 0) for d in data)
    total_sent = sum(d.get("sent", 0) for d in data)
    total_delivered = sum(d.get("delivered", 0) for d in data)
    total_read = sum(d.get("read", 0) for d in data)
    total_failed = sum(d.get("failed", 0) for d in data)

    labels = ["Queued", "Sent", "Delivered", "Read", "Failed"]
    values = [total_queued, total_sent, total_delivered, total_read, total_failed]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "Messages", "values": values}],
        },
        "type": "donut",
        "colors": ["#ffc107", "#17a2b8", "#28a745", "#007bff", "#dc3545"],
    }


def get_summary(data):
    """Return summary stats for number cards."""
    if not data:
        return []

    total = sum(d.get("total", 0) for d in data)
    failed = sum(d.get("failed", 0) for d in data)
    delivered = sum(d.get("delivered", 0) + d.get("read", 0) for d in data)
    success_rate = round((delivered / total) * 100, 1) if total > 0 else 0

    return [
        {"label": _("Total Messages"), "value": total, "indicator": "Blue"},
        {"label": _("Successfully Delivered"), "value": delivered, "indicator": "Green"},
        {"label": _("Failed"), "value": failed, "indicator": "Red"},
        {"label": _("Delivery Success Rate"), "value": f"{success_rate}%", "indicator": "Green" if success_rate >= 80 else "Red"},
    ]
