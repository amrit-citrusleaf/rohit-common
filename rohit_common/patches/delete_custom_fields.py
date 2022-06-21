# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def execute():
    # Deletes custom fields from Custom Field Table based on Dictionary
    custom_field_list = [{"dt": "Asset", "fieldname": "autoname"}
                         ]
    for fld in custom_field_list:
        custom_field = frappe.db.get_value("Custom Field", fld)
        frappe.delete_doc("Custom Field", custom_field)
        print(f"Deleted Custom Field: {custom_field} with Filters: {fld}")
