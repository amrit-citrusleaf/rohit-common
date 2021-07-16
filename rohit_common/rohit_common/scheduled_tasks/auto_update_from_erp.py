# -*- coding: utf-8 -*-
# Copyright (c) 2021, Rohit Industries Group Pvt Ltd. and contributors
# For license information, please see license.txt

# This Scheduled Tasks Would Periodically check the Sales Invoices in ERP and Update the
# Shipping Bill No and Shipping Bill Date

from __future__ import unicode_literals
import frappe
import time
from ..erpnext_api.erpnext_api_common import get_dt
from ...utils.accounts_utils import get_base_doc_no


def update_export_invoices():
    st_time = time.time()
    records_updated = 0
    exp_inv = frappe.db.sql("""SELECT si.name, si.shipping_bill_number, si.shipping_bill_date
        FROM `tabSales Invoice` si, `tabSales Taxes and Charges Template` st
        WHERE si.docstatus=1 AND si.base_net_total > 0 AND si.taxes_and_charges = st.name AND st.disabled = 0
        AND st.is_export = 1 AND si.shipping_bill_number IS NULL""", as_dict=1)
    for inv in exp_inv:
        sid = frappe.get_doc("Sales Invoice", inv.name)
        base_si_no = get_base_doc_no(sid)
        fields = ["name", "shipping_bill_number", "shipping_bill_date"]
        filters = [["docstatus", "=", 1], ["name", "LIKE", "%" + str(base_si_no) + "%"]]
        r = get_dt(dt='Sales Invoice', fields_list=fields, filters=filters)
        if r:
            if r.get("data"):
                epd = frappe._dict(r.get("data")[0])
                records_updated += 1
                frappe.db.set_value("Sales Invoice", sid.name, "shipping_bill_number", epd.shipping_bill_number)
                frappe.db.set_value("Sales Invoice", sid.name, "shipping_bill_date", epd.shipping_bill_date)
                print(f"Updated Shipping Bill No and Date in {sid.name}")
    print(f"Total Invoices Updated = {records_updated}")
    print(f"Total Time Taken = {int(time.time() - st_time)} seconds")

