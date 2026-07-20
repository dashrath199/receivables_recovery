# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import _


def execute(filters=None):
    """Promise-to-Pay Reliability Report.

    Compares promised_payment_date against actual Payment Entry date
    per customer, aggregated into a reliability percentage.

    Reliability % = (Promise Kept Count / Total Promise Count) * 100

    A promise is "kept" if a Payment Entry exists with a posting date
    on or before the promised_payment_date.
    """
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)

    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 200},
        {"label": _("Total Promises"), "fieldname": "total_promises", "fieldtype": "Int", "width": 120},
        {"label": _("Promises Kept"), "fieldname": "promises_kept", "fieldtype": "Int", "width": 120},
        {"label": _("Promises Broken"), "fieldname": "promises_broken", "fieldtype": "Int", "width": 120},
        {"label": _("Reliability (%)"), "fieldname": "reliability_pct", "fieldtype": "Percent", "width": 120},
    ]


def get_data(filters=None):
    """Fetch dunning records with promises and check if payment was received."""
    data = frappe.db.sql("""
        SELECT
            d.customer,
            COUNT(d.name) AS total_promises,
            SUM(CASE
                WHEN EXISTS (
                    SELECT 1 FROM `tabPayment Entry Reference` per
                    INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
                    WHERE per.reference_name = d.sales_invoice
                    AND pe.docstatus = 1
                    AND pe.posting_date <= d.promised_payment_date
                ) THEN 1
                ELSE 0
            END) AS promises_kept,
            SUM(CASE
                WHEN NOT EXISTS (
                    SELECT 1 FROM `tabPayment Entry Reference` per
                    INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
                    WHERE per.reference_name = d.sales_invoice
                    AND pe.docstatus = 1
                    AND pe.posting_date <= d.promised_payment_date
                ) THEN 1
                ELSE 0
            END) AS promises_broken
        FROM `tabDunning` d
        WHERE d.promised_payment_date IS NOT NULL
        GROUP BY d.customer
        ORDER BY reliability_pct ASC
    """, as_dict=1)

    for row in data:
        if row.total_promises > 0:
            row.reliability_pct = round((row.promises_kept / row.total_promises) * 100, 1)
        else:
            row.reliability_pct = 0

    return data


def get_chart(data):
    """Return bar chart — reliability % per customer."""
    if not data:
        return None

    labels = [d.get("customer", "") for d in data]
    values = [d.get("reliability_pct", 0) for d in data]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": "Reliability %", "values": values}],
        },
        "type": "bar",
        "colors": ["#28a745"],
    }


def get_summary(data):
    """Return summary stats."""
    if not data:
        return []

    total_promises = sum(d.get("total_promises", 0) for d in data)
    total_kept = sum(d.get("promises_kept", 0) for d in data)
    avg_reliability = round((total_kept / total_promises) * 100, 1) if total_promises > 0 else 0

    return [
        {"label": _("Total Promises"), "value": total_promises, "indicator": "Blue"},
        {"label": _("Overall Reliability"), "value": f"{avg_reliability}%", "indicator": "Green" if avg_reliability >= 70 else "Red"},
    ]
