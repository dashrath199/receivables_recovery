# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    """Collections Cadence Effectiveness Report.

    Shows % of Dunning records resolved at each escalation stage.
    A Dunning is "resolved" when the Sales Invoice outstanding_amount
    becomes 0 (fully paid).

    This helps measure how effective each stage is at collecting payment.
    """
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)

    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Escalation Stage"), "fieldname": "escalation_stage", "fieldtype": "Data", "width": 180},
        {"label": _("Total Dunning Records"), "fieldname": "total_count", "fieldtype": "Int", "width": 160},
        {"label": _("Resolved (Paid)"), "fieldname": "resolved_count", "fieldtype": "Int", "width": 150},
        {"label": _("Unresolved"), "fieldname": "unresolved_count", "fieldtype": "Int", "width": 130},
        {"label": _("Resolution Rate (%)"), "fieldname": "resolution_pct", "fieldtype": "Percent", "width": 150},
    ]


def get_data(filters=None):
    """Fetch dunning records grouped by escalation stage with resolution status."""
    data = frappe.db.sql("""
        SELECT
            d.escalation_stage,
            COUNT(d.name) AS total_count,
            SUM(CASE
                WHEN COALESCE(si.outstanding_amount, 0) <= 0 THEN 1
                ELSE 0
            END) AS resolved_count,
            SUM(CASE
                WHEN COALESCE(si.outstanding_amount, 0) > 0 THEN 1
                ELSE 0
            END) AS unresolved_count
        FROM `tabDunning` d
        LEFT JOIN `tabSales Invoice` si ON si.name = d.sales_invoice
        GROUP BY d.escalation_stage
        ORDER BY CASE d.escalation_stage
            WHEN 'Reminder 1' THEN 1
            WHEN 'Reminder 2' THEN 2
            WHEN 'Final Notice' THEN 3
            WHEN 'Legal Referral' THEN 4
            ELSE 5
        END
    """, as_dict=1)

    for row in data:
        if row.total_count > 0:
            row.resolution_pct = round((row.resolved_count / row.total_count) * 100, 1)
        else:
            row.resolution_pct = 0

    return data


def get_chart(data):
    """Return funnel/bar chart showing resolution rates per stage."""
    if not data:
        return None

    labels = [d.get("escalation_stage", "") for d in data]
    total_values = [d.get("total_count", 0) for d in data]
    resolved_values = [d.get("resolved_count", 0) for d in data]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Total", "values": total_values},
                {"name": "Resolved", "values": resolved_values},
            ],
        },
        "type": "bar",
        "colors": ["#6c757d", "#28a745"],
    }


def get_summary(data):
    """Return summary stats."""
    if not data:
        return []

    total = sum(d.get("total_count", 0) for d in data)
    resolved = sum(d.get("resolved_count", 0) for d in data)
    overall_rate = round((resolved / total) * 100, 1) if total > 0 else 0

    return [
        {"label": _("Total Dunning Records"), "value": total, "indicator": "Blue"},
        {"label": _("Overall Resolution Rate"), "value": f"{overall_rate}%", "indicator": "Green" if overall_rate >= 50 else "Red"},
    ]
