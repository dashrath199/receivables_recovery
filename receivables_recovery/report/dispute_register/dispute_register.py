# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    """Dispute Register Report — lists all disputed dunning records.

    Filters: dispute_flag = 1
    Shows customer, invoice, amount, dispute reason, and escalation stage.
    """
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)

    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Dunning"), "fieldname": "dunning_name", "fieldtype": "Link", "options": "Dunning", "width": 160},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
        {"label": _("Outstanding Amount"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 140},
        {"label": _("Dispute Reason"), "fieldname": "dispute_reason", "fieldtype": "Small Text", "width": 300},
        {"label": _("Escalation Stage"), "fieldname": "escalation_stage", "fieldtype": "Data", "width": 140},
        {"label": _("Last Contact"), "fieldname": "last_contact_channel", "fieldtype": "Data", "width": 120},
        {"label": _("Promised Payment Date"), "fieldname": "promised_payment_date", "fieldtype": "Date", "width": 160},
    ]


def get_data(filters=None):
    """Fetch disputed dunning records."""
    conditions = ""
    if filters and filters.get("customer"):
        conditions = f"AND d.customer = {frappe.db.escape(filters['customer'])}"

    data = frappe.db.sql(f"""
        SELECT
            d.name AS dunning_name,
            d.customer,
            d.sales_invoice,
            COALESCE(si.outstanding_amount, 0) AS outstanding_amount,
            d.dispute_reason,
            d.escalation_stage,
            d.last_contact_channel,
            d.promised_payment_date
        FROM `tabDunning` d
        LEFT JOIN `tabSales Invoice` si ON si.name = d.sales_invoice
        WHERE d.dispute_flag = 1
            {conditions}
        ORDER BY d.creation DESC
    """, as_dict=1)

    return data


def get_chart(data):
    """Pie chart: disputed amounts by escalation stage."""
    if not data:
        return None

    # Group by escalation stage
    stages = {}
    for d in data:
        stage = d.get("escalation_stage", "Unknown")
        stages[stage] = stages.get(stage, 0) + (d.get("outstanding_amount", 0) or 0)

    labels = list(stages.keys())
    values = list(stages.values())

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "Disputed Amount", "values": values}],
        },
        "type": "pie",
        "colors": ["#dc3545", "#fd7e14", "#ffc107", "#6f42c1"],
    }


def get_summary(data):
    """Return summary stats."""
    if not data:
        return []

    total_disputed = sum(d.get("outstanding_amount", 0) or 0 for d in data)
    count = len(data)

    return [
        {"label": _("Total Disputed Records"), "value": count, "indicator": "Blue"},
        {"label": _("Total Disputed Amount (₹)"), "value": total_disputed, "indicator": "Red"},
    ]
