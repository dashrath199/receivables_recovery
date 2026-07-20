// Copyright (c) 2026, Receivables Recovery and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Dispute Register"] = {
	"filters": [
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		}
	],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "outstanding_amount" && value > 0) {
			value = `<span style="color:red; font-weight:bold;">${value}</span>`;
		}
		return value;
	}
};
