# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    """Aging Bucket Summary Report — 0-30 / 31-60 / 61-90 / 90+ buckets.

    Returns columns and data for a stacked bar chart showing outstanding
    amounts per aging bucket, optionally filtered by customer.
    """
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)

    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
        {"label": _("0-30 Days"), "fieldname": "bucket_0_30", "fieldtype": "Currency", "width": 120},
        {"label": _("31-60 Days"), "fieldname": "bucket_31_60", "fieldtype": "Currency", "width": 120},
        {"label": _("61-90 Days"), "fieldname": "bucket_61_90", "fieldtype": "Currency", "width": 120},
        {"label": _("90+ Days"), "fieldname": "bucket_90_plus", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Outstanding"), "fieldname": "total_outstanding", "fieldtype": "Currency", "width": 140},
    ]


def get_data(filters=None):
    """Fetch overdue invoices and bucket them by days overdue."""
    conditions = ""
    if filters and filters.get("customer"):
        conditions = f"AND si.customer = {frappe.db.escape(filters['customer'])}"

    data = frappe.db.sql(f"""
        SELECT
            si.customer,
            SUM(CASE WHEN DATEDIFF(CURDATE(), si.due_date) BETWEEN 0 AND 30 THEN si.outstanding_amount ELSE 0 END) AS bucket_0_30,
            SUM(CASE WHEN DATEDIFF(CURDATE(), si.due_date) BETWEEN 31 AND 60 THEN si.outstanding_amount ELSE 0 END) AS bucket_31_60,
            SUM(CASE WHEN DATEDIFF(CURDATE(), si.due_date) BETWEEN 61 AND 90 THEN si.outstanding_amount ELSE 0 END) AS bucket_61_90,
            SUM(CASE WHEN DATEDIFF(CURDATE(), si.due_date) > 90 THEN si.outstanding_amount ELSE 0 END) AS bucket_90_plus,
            SUM(si.outstanding_amount) AS total_outstanding
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
            AND si.outstanding_amount > 0
            AND si.due_date < CURDATE()
            {conditions}
        GROUP BY si.customer
        ORDER BY total_outstanding DESC
    """, as_dict=1)

    return data


def get_chart(data):
    """Return stacked bar chart configuration."""
    if not data:
        return None

    labels = [d.get("customer", "") for d in data]
    datasets = [
        {"name": "0-30 Days", "values": [d.get("bucket_0_30", 0) for d in data]},
        {"name": "31-60 Days", "values": [d.get("bucket_31_60", 0) for d in data]},
        {"name": "61-90 Days", "values": [d.get("bucket_61_90", 0) for d in data]},
        {"name": "90+ Days", "values": [d.get("bucket_90_plus", 0) for d in data]},
    ]

    return {
        "data": {
            "labels": labels,
            "datasets": datasets,
        },
        "type": "bar",
        "barOptions": {"stacked": True},
        "colors": ["#28a745", "#ffc107", "#fd7e14", "#dc3545"],
    }


def get_summary(data):
    """Return summary number cards."""
    if not data:
        return []

    total_overdue = sum(d.get("total_outstanding", 0) for d in data)
    total_90_plus = sum(d.get("bucket_90_plus", 0) for d in data)

    return [
        {"label": _("Total Overdue (₹)"), "value": total_overdue, "indicator": "Blue"},
        {"label": _("90+ Days Overdue (₹)"), "value": total_90_plus, "indicator": "Red"},
    ]
