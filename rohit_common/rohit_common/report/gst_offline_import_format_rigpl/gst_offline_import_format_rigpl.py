# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	if filters.get("item_wise") == 1:
		columns = [
				_("Invoice Number") + ":Link/Sales Invoice:100",
				_("Invoice Date") + ":Date:80", _("Grand Total") + ":Currency:80",
				_("Net Total") + ":Currency:80", _("Customer") + ":Link/Customer:200",
				_("Ship Address") + ":Link/Address:200", 
				_("Tax") + ":Link/Sales Taxes and Charges Template:150", 
				_("Ship Country") + ":Link/Country:150" 
			]
	elif filters.get("hsn") == 1:
		columns = [
				_("Item Code") + ":Link/Item:100",
				_("HSN Code") + "::80", _("Quantity") + ":Float:80", _("UoM") + "::80",
				_("Grand Total") + ":Currency:120", _("Net Total") + ":Currency:120",
				_("IGST Amount") + ":Currency:120", _("CGST Amount") + ":Currency:120",
				_("SGST Amount") + ":Currency:120"
			]
	else:
		columns = [
			_("Invoice Date") + ":Date:90", _("Invoice Number") + ":Link/Sales Invoice:120",
			_("Net Total") + ":Currency:100", _("Grand Total") + ":Currency:100",
			_("Customer Link") + ":Link/Customer:100", 
			_("Tax Link") + ":Link/Sales Taxes and Charges Template:100",
			_("Is Export") + ":Int:30", _("GST Paid on Export") + ":Int:30",
			_("Export Shipping Bill Number") + "::80", _("Export Shipping Bill Date") + ":Date:80",
			_("Export Shipping Bill Port Code") + "::80", _("Export Destination Country Code") + "::80",
			_("Billing Address Link") + ":Link/Address:80", _("Billing Name") + "::80",
			_("Billing City") + "::80", _("Billing Pincode") + "::60", _("Billing State") + "::80",
			_("Billing GSTIN") + "::140",
			_("Shipping Address Link") + ":Link/Address:80", _("Shipping Name") + "::80",
			_("Shipping City") + "::80", _("Shipping Pincode") + "::60", _("Shipping State") + "::80",
			_("Shipping GSTIN") + "::140",
			_("CGST Rate") + ":Percent:50", _("CGST Amount") + ":Currency:80",
			_("SGST Rate") + ":Percent:50", _("SGST Amount") + ":Currency:80",
			_("IGST Rate") + ":Percent:50", _("IGST Amount") + ":Currency:80"
			]
	return columns

def get_data(filters):
	si_cond = get_conditions(filters)
	if filters.get("item_wise") == 1:
		data = frappe.db.sql("""SELECT si.name, si.posting_date, si.base_grand_total,
			si.base_net_total,si.customer, si.shipping_address_name, si.taxes_and_charges,
			ad.country
			FROM `tabSales Invoice` si, `tabSales Taxes and Charges Template` stct, `tabAddress` ad
			WHERE stct.name = si.taxes_and_charges AND ad.name = si.shipping_address_name
				AND si.docstatus = 1 AND stct.is_export = 1 %s
			ORDER BY si.posting_date, si.name""" %(si_cond), as_list=1)
	elif filters.get("hsn") == 1:
		data = frappe.db.sql("""SELECT sid.item_code, it.customs_tariff_number, SUM(sid.qty),
			it.stock_uom, SUM(sid.base_amount), SUM(sid.base_net_amount)
			FROM `tabSales Invoice` si, `tabSales Invoice Item` sid, `tabItem` it
			WHERE si.docstatus = 1 AND sid.parent = si.name 
				AND sid.item_code = it.name %s
			GROUP BY sid.item_code
			ORDER BY sid.item_code""" %(si_cond), as_list = 1)
	else:
		data = frappe.db.sql("""SELECT si.posting_date, si.name, si.base_net_total,
			si.base_grand_total, si.customer, si.taxes_and_charges, 
			tax_template.is_export, 0, 'EXP_SHIP_BILL', 'SHIP_DATE', 
			'SHIP_PORT_CODE', 'COUNTRY CODE', 
			si.customer_address, ad.address_title, ad.city, ad.pincode, ad.state_rigpl, 
			ad.gstin,
			si.shipping_address_name, ad2.address_title, ad2.city, ad2.pincode, ad2.state_rigpl,
			ad2.gstin
			FROM `tabSales Invoice` si, `tabAddress` ad, `tabAddress` ad2,
				`tabSales Taxes and Charges Template` tax_template, 
				`tabSales Taxes and Charges` tax
			WHERE ad.name = si.customer_address 
				AND ad2.name = si.shipping_address_name
				AND si.taxes_and_charges = tax_template.name
				AND tax.parent = si.name
				AND si.docstatus != 2 %s""" %(si_cond), as_list=1)
	return data


def get_conditions(filters):
	if filters.get("item_wise") == 1 and filters.get("hsn") == 1:
		frappe.throw("Only one checkbox allowed to be checked at a given time.")
	si_cond = ""
	
	if filters.get("customer"):
		si_cond += " AND si.customer = '%s'" %filters["customer"]

	if filters.get("from_date"):
		si_cond += " AND si.posting_date >= '%s'" %filters["from_date"]

	if filters.get("to_date"):
		si_cond += " AND si.posting_date <= '%s'" %filters["to_date"]

	if filters.get("letter_head"):
		si_cond += " AND si.letter_head = '%s'" %filters["letter_head"]

	if filters.get("taxes"):
		si_cond += " AND si.taxes_and_charges = '%s'" %filters["taxes"]

	return si_cond