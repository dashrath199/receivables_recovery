# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def get_data():
    return {
        "category": "Modules",
        "icon": "octicon octicon-graph",
        "label": "Receivables & Collections",
        "type": "module",
        "links": [
            {
                "label": "Dunning",
                "type": "doctype",
                "name": "Dunning",
            },
            {
                "label": "Sales Invoice (Overdue)",
                "type": "report",
                "is_query_report": True,
                "name": "Aging Bucket Summary",
            },
            {
                "label": "Collections Cadence Rules",
                "type": "doctype",
                "name": "Collections Cadence Rule",
            },
            {
                "label": "Message Templates",
                "type": "doctype",
                "name": "Message Template",
            },
            {
                "label": "Communication Log",
                "type": "doctype",
                "name": "Communication Log",
            },
            {
                "label": "Reports",
                "type": "reports",
                "items": [
                    {
                        "label": "Aging Bucket Summary",
                        "type": "report",
                        "is_query_report": True,
                        "name": "Aging Bucket Summary",
                    },
                    {
                        "label": "Promise-to-Pay Reliability",
                        "type": "report",
                        "is_query_report": False,
                        "name": "Promise-to-Pay Reliability",
                    },
                    {
                        "label": "Collections Cadence Effectiveness",
                        "type": "report",
                        "is_query_report": False,
                        "name": "Collections Cadence Effectiveness",
                    },
                    {
                        "label": "Dispute Register",
                        "type": "report",
                        "is_query_report": True,
                        "name": "Dispute Register",
                    },
                    {
                        "label": "Message Delivery Report",
                        "type": "report",
                        "is_query_report": True,
                        "name": "Message Delivery Report",
                    },
                ],
            },
        ],
    }
