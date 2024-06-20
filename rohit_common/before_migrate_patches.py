# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import frappe

def execute():
    frappe.reload_doc("Custom", "DocType", "Client Script")
    frappe.reload_doc("Accounts", "DocType", "POS Invoice")
    frappe.reload_doc("Accounts", "DocType", "POS Invoice Item")