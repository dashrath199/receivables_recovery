// Copyright (c) 2026, Receivables Recovery and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Promise-to-Pay Reliability"] = {
	"filters": [],
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "reliability_pct" && value < 50) {
			value = `<span style="color:red; font-weight:bold;">${value}</span>`;
		} else if (column.fieldname === "reliability_pct" && value >= 70) {
			value = `<span style="color:green; font-weight:bold;">${value}</span>`;
		}
		return value;
	}
};
