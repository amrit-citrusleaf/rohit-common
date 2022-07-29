// Copyright (c) 2016, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Asset Analysis"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": "From Date",
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			"fieldname":"to_date",
			"label": "To Date",
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
		},
		{
			"fieldname":"asset_category",
			"label": "Asset Category",
			"fieldtype": "Link",
			"options": "Asset Category"
		},
		{
			"fieldname":"asset",
			"label": "Asset",
			"fieldtype": "Link",
			"options": "Asset"
		},
		{
			"fieldname":"account",
			"label": "Account",
			"fieldtype": "Link",
			"options": "Account",
			"get_query": function(){ return {'filters': [['Account', 'account_type','=', 'Fixed Asset']]}}
		},
		{
			"fieldname":"compare_accounts",
			"label": "Compare Accounts",
			"fieldtype": "Check",
			"default": 1,
		},
	]
}
