// Copyright (c) 2026, Receivables Recovery and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Message Delivery Report"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "channel",
			"label": __("Channel"),
			"fieldtype": "Select",
			"options": ["", "WhatsApp", "SMS", "Email", "Call"]
		}
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "failed" && value > 0) {
			value = `<span style="color:red; font-weight:bold;">${value}</span>`;
		}
		if (column.fieldname === "delivery_rate" && value < 50) {
			value = `<span style="color:red; font-weight:bold;">${value}</span>`;
		} else if (column.fieldname === "delivery_rate" && value >= 90) {
			value = `<span style="color:green; font-weight:bold;">${value}</span>`;
		}
		return value;
	}
};
