# -*- coding: utf-8 -*-
# Copyright (c) 2020, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from datetime import timedelta
from frappe.model.document import Document
from frappe.desk.reportview import get_match_cond, get_filters_cond
from frappe.utils import flt
from ...india_gst_api.eway_bill_api import *
from ...validations.sales_invoice import get_item_synopsis
from ...validations.google_maps import get_distance_matrix, get_approx_dist_frm_matrix


class eWayBill(Document):
    def create_ewb(self):
        """
        Creates an Eway Bill for an Eway Bill Doc
        """
        if not self.json_reply and not self.eway_bill_no:
            ewb_json = self.get_ewb_json(self.document_type, self.document_number)
            frappe.msgprint(str(ewb_json))
            json_reply = create_ewb_from_json(ewb_json)
            frappe.msgprint(str(json_reply))
            if json_reply:
                if json_reply.get('status_cd', 1) == 1:
                    self.json_reply = str(json_reply)
                    self.eway_bill_no = json_reply.get('ewayBillNo')
                    self.eway_bill_date = datetime.strptime(json_reply.get('ewayBillDate'), '%d/%m/%Y %I:%M:%S %p')
                    return json_reply.get('ewayBillNo')
                else:
                    frappe.msgprint("Got Error")
                    error = json_reply.get('error')
                    if error.get('error_cd') == '604,':
                        # Search for eWay Bill by Doctype and Document Number and get details for the same.
                        res_json = get_ewb_by_dt_dn(dt=self.ewb_document_type, dn=self.document_number)
                        self.eway_bill_no = res_json.get('ewayBillNo')
                        self.eway_bill_date = datetime.strptime(res_json.get('ewayBillDate'), '%d/%m/%Y %I:%M:%S %p')
                        self.save()
                        self.reload()
        else:
            frappe.throw(f"eWay Bill Already Generated for {self.name}")

    def update_ewb_partb(self):
        if not self.valid_upto:
            # Update Part-B
            res_json = update_partb_ewb(self)
            self.valid_upto = datetime.strptime(res_json.get('validUpto'), '%d/%m/%Y %I:%M:%S %p')
            self.save()
            self.reload()

    def get_eway_bill_print(self):
        """
        Gets Detailed print for an eWay Bill Doctype if needed
        """
        if self.eway_bill_no:
            if self.valid_upto:
                query = f"""SELECT name FROM `tabFile`
                WHERE file_name LIKE '{self.eway_bill_no}.pdf' AND
                attached_to_doctype = '{self.doctype}' AND attached_to_name = '{self.name}'"""
                file_list = frappe.db.sql(query, as_list=1)
                if not file_list:
                    if self.json_reply:
                        json_data = json.loads((self.json_reply).replace("'", '"'))
                        get_ewb_detailed_print(ewbdoc=self, json_data=json_data)
                        self.reload()
                    else:
                        res_json = get_eway_bill_details(self.eway_bill_no)
                        get_ewb_detailed_print(ewbdoc=self, json_data=res_json)
                else:
                    frappe.throw(f"eWay Bill print already attached for \
                        {frappe.get_desk_link(self.doctype, self.name)}")
            else:
                frappe.throw(f"{frappe.get_desk_link(self.doctype,self.name)} is Not Valid Update \
                    Part-B First")
        else:
            frappe.throw(f"eWay Bill No not generated for \
                {frappe.get_desk_link(self.doctype,self.name)}")


    def get_eway_bill(self):
        """
        Gets the EWay Bill Details for a eWay Bill No
        """
        if self.eway_bill_no:
            json_reply = get_eway_bill_details(self.eway_bill_no)
            self.json_reply = str(json_reply)
            ewb_from_ewb_detail(json_reply)
            self.get_eway_bill_print()
        else:
            frappe.throw(f"No eWay Bill number mentioned for \
                {frappe.get_desk_link('eWay Bill', self.name)}")


    def get_ewb_json(self, dt, dn):
        doc = frappe.get_doc(dt, dn)
        data = frappe._dict({"TotNonAdvolVal": 0, })
        data = get_transporter_id(data, dt, dn, self)
        data = get_supply_type(data, self.supply_type)
        data = get_supply_sub_type(data, self.supply_sub_type)
        data = get_doctype(data=data, text=self.ewb_document_type)
        data = get_docno(data, dt, dn)
        data = get_from_address_doc(self, data, 'from')
        data = get_from_address_doc(self, data, 'to')
        data = get_value_of_tax(data, self)
        data = get_doc_date(data, dt, dn)
        data = get_trans_type(data, self.transaction_type)
        data = get_items_table(data, self.items)
        data.transDistance = self.approx_distance
        return data

    def validate(self, created_by_api=0):
        if self.get('__islocal') == 1:
            enforce = 0
            if self.document_type and self.document_number:
                self.created_by_api = 1
        else:
            self.check_eway_bill_no()
            enforce = 1
        created_by_api = self.created_by_api
        if created_by_api == 1:
            self.check_other_ewb()
            self.update_and_validate_fields()
            self.get_vehicle_details()
            self.validate_vehicle_details(enforce=enforce)

    def check_eway_bill_no(self):
        if self.eway_bill_no:
            self.docstatus = 1

    def update_and_validate_fields(self):
        rset = frappe.get_single('Rohit Settings')
        gstin = frappe.get_value("Rohit Settings", "Rohit Setttings", "gstin")
        self.update_tax_related_fields()
        frm_add_doc = frappe.get_doc('Address', self.from_address)
        to_add_doc = frappe.get_doc('Address', self.to_address)
        self.get_distance(frm_add_doc, to_add_doc)
        if self.document_type == 'Sales Invoice':
            if self.generated_by and self.generated_by != gstin and rset.sandbox_mode != 1:
                frappe.throw('GSTIN for Company is Needed in Generated By for {}'.format(self.document_type))
        elif self.document_type == 'Purchase Order':
            pass
        else:
            if self.document_type:
                frappe.throw('Not Allowed for {}'.format(self.document_type))

    def update_tax_related_fields(self):
        doc = frappe.get_doc(self.document_type, self.document_number)
        if self.document_type == 'Sales Invoice':
            self.supply_type = 'Outward'
            self.ewb_document_type = 'Tax Invoice'
            si_tax = frappe.get_doc('Sales Taxes and Charges Template', doc.taxes_and_charges)
            if si_tax.is_export == 1:
                self.supply_sub_type = 'Export'
            else:
                self.supply_sub_type = 'Supply'
        elif self.document_type == 'Purchase Order':
            po_tax = frappe.get_doc('Purchase Taxes and Charges Template', doc.taxes_and_charges)
            if doc.is_subcontracting == 1:
                self.supply_type = 'Outward'
                self.supply_sub_type = 'Job Work'
                self.ewb_document_type = 'Delivery Challan'
            elif po_tax.is_import == 1:
                self.supply_type = 'Inward'
                self.supply_sub_type = 'Import'
                self.ewb_document_type = 'Bill of Entry'
        it_list, needs_update = get_item_synopsis(doc)
        if not self.items:
            for d in it_list:
                self.append("items", d.copy())
        taxes_dict = get_taxes_type(self.document_type, self.document_number)
        self.sgst_value = round(taxes_dict.get('sgst_amt', 0),0)
        self.cgst_value = round(taxes_dict.get('cgst_amt', 0),0)
        self.igst_value = round(taxes_dict.get('igst_amt', 0),0)
        self.cess_value = round(taxes_dict.get('cess_amt', 0), 0)
        self.taxable_value = round(doc.base_net_total,0)
        self.total_value = round(doc.base_grand_total, 0)
        self.other_value = self.total_value - (self.taxable_value + self.sgst_value + self.cgst_value +
                                                                                   self.igst_value + self.cess_value)
        for d in self.items:
            d.sgst_rate = taxes_dict.get('sgst_per', 0)
            d.cgst_rate = taxes_dict.get('cgst_per', 0)
            d.igst_rate = taxes_dict.get('igst_per', 0)
        self.update_address_fields(doc)

    def update_address_fields(self, oth_doc):
        # Get the Tax Template Doc
        if oth_doc.doctype == 'Purchase Order':
            tx_doc = frappe.get_doc('Purchase Taxes and Charges Template', oth_doc.taxes_and_charges)
        elif oth_doc.doctype == 'Sale Invoice':
            tx_doc = frappe.get_doc('Sales Taxes and Charges Template', oth_doc.taxes_and_charges)

        # Get the From and To Address
        if oth_doc.doctype == 'Sales Invoice':
            self.from_address = oth_doc.company_address
            self.to_address = oth_doc.shipping_address_name
            if oth_doc.customer_address == oth_doc.shipping_address_name:
                self.transaction_type = 'Regular'
            else:
                self.transaction_type = 'Bill To - Ship To'
        elif oth_doc.doctype == 'Purchase Order' and oth_doc.is_subcontracting == 1:
            self.transaction_type = 'Regular'
            self.from_address = oth_doc.billing_address
            self.to_address = oth_doc.supplier_address
        elif oth_doc.doctype == 'Purchase Order' and tx_doc.is_import == 1:
            if oth_doc.shipping_address == oth_doc.billing_address:
                self.transaction_type = 'Regular'
            else:
                self.transaction_type = 'Bill To - Ship To'
            self.from_address = oth_doc.supplier_address
            self.to_address = oth_doc.shipping_address

        # Update the Fields from Address Doc
        frm_add_doc = frappe.get_doc('Address', self.from_address)
        to_add_doc = frappe.get_doc('Address', self.to_address)
        self.update_from_add_doc(frm_add_doc, text='from')
        self.update_from_add_doc(to_add_doc, text='to')

    def update_from_add_doc(self, add_doc, text):
        rset = frappe.get_single("Rohit Settings")
        if rset.sandbox_mode == 1:
            setattr(self, 'generated_by', '05AAACG1539P1ZH')
            if text == 'to' and self.supply_type == 'Inward':
                self.update_sandbox_details(text)
            elif text == 'from' and self.supply_type == 'Outward':
                self.update_sandbox_details(text)
            else:
                self.update_sandbox_details(text)
        else:
            if add_doc.country == 'India':
                self.update_actual_details(text, add_doc)
                if text == 'to' and self.supply_type == 'Inward':
                    setattr(self, 'generated_by', add_doc.get('gstin'))
                elif text == 'from' and self.supply_type == 'Outward':
                    setattr(self, 'generated_by', add_doc.get('gstin'))
            else:
                self.update_actual_details(text, add_doc)

    def update_actual_details(self, text, add_doc):
        if add_doc.country == 'India':
            setattr(self, text + '_pincode', add_doc.get('pincode'))
            setattr(self, text + '_state_code', add_doc.get('gst_state_number'))
            setattr(self, text + '_gstin', add_doc.get('gstin'))
        else:
            setattr(self, text + '_pincode', 999999)
            setattr(self, text + '_state_code', 99)
            setattr(self, text + '_gstin', 'URP')

    def update_sandbox_details(self, text):
        if text == 'from':
            setattr(self, text + 'generated_by', '05AAACG1539P1ZH')
            setattr(self, text + '_gstin', '05AAACG1539P1ZH')
            setattr(self, text + '_state_code', 5)
            setattr(self, text + '_pincode', 263652)
        elif text == 'to':
            setattr(self, text + '_gstin', '02EHFPS5910D2Z0')
            setattr(self, text + '_state_code', 2)
            setattr(self, text + '_pincode', 176036)

    def get_distance(self, frm_add_doc, to_add_doc):
        if frm_add_doc.country == to_add_doc.country:
            dist_matrix = get_distance_matrix(origin=frm_add_doc.pincode, dest=to_add_doc.pincode)
            distance = get_approx_dist_frm_matrix(dist_matrix)
        else:
            distance = 99
        if not self.approx_distance:
            self.approx_distance = self.get_approx_dist_ewb(distance)
        if self.approx_distance > 4000:
            frappe.throw("Approx Distance cannot be greater than 4000 kms")

    def check_other_ewb(self):
        other_ewb = frappe.db.sql("""SELECT name FROM `tabeWay Bill` WHERE eway_bill_no = '%s'
        AND name != '%s' AND docstatus != 2""" %(self.eway_bill_no, self.name), as_list=1)
        if other_ewb:
            frappe.throw('{} Already Exists with Same eWay Bill No {}'.
                                     format(frappe.get_desk_link(self.doctype, other_ewb[0][0]), self.eway_bill_no))
        other_ewb_dt = frappe.db.sql("""SELECT name FROM `tabeWay Bill` WHERE document_type = '%s'
            AND document_number = '%s' AND docstatus != 2 AND name != '%s'"""%
                                                                 (self.document_type,self.document_number, self.name), as_list=1)
        if other_ewb_dt:
            frappe.throw('{} already exists for {}'.format(frappe.get_desk_link(self.doctype, other_ewb_dt[0][0]),
                                                                                                       frappe.get_desk_link(self.document_type,
                                                                                                                                                    self.document_number)))

    def get_vehicle_details(self):
        if self.document_type in ('Sales Invoice', 'Purchase Order'):
            self.update_vehicle_details()
        else:
            if not self.vehicles:
                frappe.throw('Vehicles Table is Mandatory')

    def update_vehicle_details(self):
        frm_add = frappe.get_doc('Address', self.from_address)
        self.vehicles = []
        veh = {}
        si_doc = frappe.get_doc(self.document_type, self.document_number)
        trans_doc = frappe.get_doc('Transporters', si_doc.transporters)
        if trans_doc.self_pickup == 1:
            veh["vehicle_number"] = si_doc.lr_no
        else:
            veh["transport_doc_no"] = si_doc.lr_no
            if self.document_type == 'Sales Invoice':
                veh["transport_doc_date"] = si_doc.removal_date
            else:
                veh["transport_doc_date"] = datetime.today()
        veh["mode_of_transport"] = trans_doc.mode_of_transport
        veh["from_place"] = frm_add.city
        veh["from_state_number"] = int(self.from_state_code)
        self.append("vehicles", veh.copy())

    def validate_vehicle_details(self, enforce=0):
        message = "One of Vehicle Number or Transporter Doc is Mandatory for {}".\
                format(frappe.get_desk_link(self.doctype, self.name))
        message_date = "Transporter Date is Needed with Transporter Doc for {}".\
                format(frappe.get_desk_link(self.doctype, self.name))
        message_empty = "Transporter  or Vehicle Details Needed for {}".\
                format(frappe.get_desk_link(self.doctype, self.name))
        if self.vehicles:
            for veh in self.vehicles:
                if not veh.vehicle_number and not veh.transport_doc_no:
                    if enforce == 1:
                        frappe.throw(message)
                    else:
                        frappe.msgprint(message)
                if not veh.transport_doc_date and veh.transport_doc_no:
                    if enforce == 1:
                        frappe.throw(message_date)
                    else:
                        frappe.msgprint(message_date)
        else:
            if enforce == 1:
                frappe.throw(message_empty)
            else:
                frappe.msgprint(message_empty)

    def on_submit(self):
        if not self.from_gstin or not self.to_gstin or not self.from_pincode or not self.to_pincode:
            frappe.throw('Not All fields filled. Fill the fields to submit')

        if self.taxable_value == 0:
            frappe.throw('Taxable Value cannot be Zero')

        if not self.eway_bill_no:
            frappe.throw('Eway Bill No is Mandatory for Submission')

    def on_update_after_submit(self):
        self.validate()

    def get_approx_dist_ewb(self, dist):
        return ((int(dist / 100) + 1) * 100) - 1

    def extend_eway_validity(self):
        # eWay bill validity can only be extended by Transporter or if No Transporter is defined then by Generator
        # eWay bill validity can only be extended 8 hrs before or after expiry of eWay Bill
        if self.eway_bill_no and self.valid_upto:
            valid_upto = get_datetime(self.valid_upto)
            upper_limit = valid_upto + timedelta(hours=8)
            lower_limit = valid_upto - timedelta(hours=8)
            if lower_limit < datetime.now() < upper_limit:
                frappe.msgprint('Can Extend Validity')
            else:
                frappe.throw('Validity of {} can only be Extended Between {} and {}'.
                                         format(frappe.get_desk_link(self.doctype, self.name), lower_limit, upper_limit))

    def cancel_ewb(self):
        if self.eway_bill_no:
            if get_datetime(self.eway_bill_date) + timedelta(hours=24) > datetime.now():
                # You can cancel eWay Bill only within first 24 hours of creation
                # First Cancel Invoice and then Cancel eWay Bill if all goes well then cancel eWB doc
                frappe.msgprint('You can cancel {}'.format(frappe.get_desk_link(self.doctype, self.name)))
            else:
                frappe.throw('{} Created More than 24 hours and hence cannot cancel'.
                                         format(frappe.get_desk_link(self.doctype, self.name)))

    def on_cancel(self):
        self.cancel_ewb()

@frappe.whitelist()
def ewb_po_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
    query = """SELECT po.name, po.supplier, po.transaction_date
    FROM `tabPurchase Order` po, `tabPurchase Taxes and Charges Template` tx
    WHERE (po.is_subcontracting = 1 OR tx.is_import = 1) AND po.docstatus = 1
    AND po.taxes_and_charges = tx.name AND po.status in ('To Receive and Bill', 'To Receive')
    AND (po.name LIKE {txt} OR po.supplier LIKE {txt})
    ORDER BY po.name DESC""".format(txt = frappe.db.escape('%{0}%'.format(txt)))
    return frappe.db.sql(query, as_dict=as_dict)
