# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re
import frappe
from frappe.utils import get_files_path


def santize_listed_txt_fields(document, field_dict):
    """
    Does various operations on text fields based on field_dict
    field_dict is a dictionary with field_name and also the case of the field
    1. Strips All text fields (removed leading and trailing spaces)
    2. Removes extra spaces
    3. Make the field as per cases
    """
    for fld in field_dict:
        field_name = fld.get("field_name")
        casing = fld.get("case")
        if getattr(document, field_name):
            stripped_fld = getattr(document, field_name).strip()
            if stripped_fld:
                # Below code replaces all the extra spaces
                snt_strip = " ".join(stripped_fld.split())
                if snt_strip:
                    if casing == "title":
                        cased_txt = snt_strip.title()
                    elif casing == "upper":
                        cased_txt = snt_strip.upper()
                    elif casing == "lower":
                        cased_txt = snt_strip.lower()
                    else:
                        cased_txt = snt_strip
                    setattr(document, field_name, cased_txt)
            else:
                setattr(document, field_name, None)
        else:
            setattr(document, field_name, None)



def separate_csv_in_table(document, tbl_name, field_name):
    """
    Moves the Comma Separated Values in a documents Child Table to Separate Rows
    Example Contact Emails should have single email per line instead of comma separated values
    Similarly Phones table should not have comma separated values in Phone Child table of Contact
    """
    new_tbl_rows = []
    tbl_change = 0
    tbl_lst = document.get(tbl_name)
    for csv_row in tbl_lst:
        row_list = (csv_row.get(field_name)).split(",")
        if len(row_list) > 1:
            tbl_change = 1
            for row in row_list:
                if row_list.index(row) == 0:
                    new_row = csv_row.__dict__
                    new_row[field_name] = row
                    new_tbl_rows.append(new_row.copy())
                else:
                    new_row = csv_row.__dict__
                    del new_row["name"]
                    del new_row["idx"]
                    new_row[field_name] = row
                    new_tbl_rows.append(new_row.copy())
        else:
            new_tbl_rows.append(csv_row.__dict__.copy())
    if tbl_change == 1:
        if new_tbl_rows:
            document.set(tbl_name, "")
            document.set(tbl_name, new_tbl_rows)


def get_country_code(country=None, all_caps=1, backend=True):
    """
    Returns the country code in ALL CAPS if all_caps=1 else in lower
    Also if backend is true it returns None for no country but would
    throw error is backend is false
    """
    ccode = frappe.get_value("Country", country, "code")
    if ccode:
        if all_caps == 1:
            ccode = ccode.upper()
        else:
            ccode = ccode.lower()
        return ccode
    else:
        message = f"For Country = {country} there is No Country Code defined"
        if backend == 1:
            print(message)
        else:
            frappe.msgprint(message)
        return None


def remove_html(html_text):
    """
    Cleans html tags from html text and return plain text
    """
    cleanr = re.compile(r'<(?!br).*?>')
    cleantext = cleanr.sub('', html_text)
    return cleantext


def check_system_manager(user):
    """
    Returns boolean for a system manager user
    """
    sys_list = frappe.db.sql(f"""SELECT name FROM `tabHas Role` WHERE parenttype = 'User'
        AND parent = '{user}' AND role = 'System Manager'""", as_list=1)
    if sys_list:
        return 1
    else:
        return 0


def rebuild_tree(doctype, parent_field, group_field):
    # call rebuild_node for all root nodes
    # get all roots
    lft = 1
    result = frappe.db.sql("SELECT name, %s, lft, rgt FROM `tab%s` WHERE `%s`='' or `%s` IS NULL "
                           "ORDER BY name ASC" % (group_field, doctype, parent_field, parent_field), as_dict=1)
    for r in result:
        if r.get(group_field) == 1:
            rebuild_group(doctype, parent_field, r.name, group_field, lft)
        else:
            frappe.db.sql("""UPDATE `tab%s` SET lft=%s, rgt=%s WHERE name='%s'""" % (doctype, lft, lft+1, r.name))
            lft += 2


def rebuild_group(doctype, parent_field, parent, group_field, left):
    right = left + 1
    non_gp_query = """SELECT name, %s, lft, rgt FROM `tab%s` WHERE %s = '%s'
    AND %s = 0""" % (group_field, doctype, parent_field, parent, group_field)
    non_grp_results = frappe.db.sql(non_gp_query, as_dict=1)
    for r in non_grp_results:
        frappe.db.sql("""UPDATE `tab%s` SET lft=%s, rgt=%s WHERE name='%s'""" % (doctype, right, right+1, r.name))
        right += 2
    grp_result = frappe.db.sql("""SELECT name, %s FROM `tab%s` WHERE %s = '%s'
    AND %s = 1""" % (group_field, doctype, parent_field, parent, group_field), as_dict=1)
    for r in grp_result:
        print(f"Updating Groups for {r.name}")
        right = rebuild_group(doctype, parent_field, r.name, group_field, right)
    frappe.db.sql("""UPDATE `tab%s` SET lft=%s, rgt=%s WHERE name='%s'""" % (doctype, left, right, parent))
    return right


def move_file_folder(file_name, old_folder, new_folder, is_folder=0):
    frappe.msgprint(f"File={file_name} OldFolder={old_folder} NewFolder={new_folder} IsFolder={is_folder}")


def get_folder_details(folder_name):
    return frappe.db.sql("""SELECT name, parent, parentfield, parenttype, idx, file_name, attached_to_doctype, rgt,
    lft, (rgt-lft) as diff,is_home_folder, is_folder, folder, is_private, attached_to_field
    FROM `tabFile` WHERE name = '%s'""" % folder_name, as_dict=1)


def make_file_path(file_doc):
    if file_doc.is_private == 1:
        fpath = get_files_path(is_private=1)
    else:
        fpath = get_files_path()
    return fpath + '/' + file_doc.file_name


def get_email_id(email_id):
    if email_id:
        if email_id != "NA":
            return email_id
        else:
            return ""


def check_sales_taxes_integrity(document):
    template = frappe.get_doc("Sales Taxes and Charges Template", document.taxes_and_charges)
    if len(template.taxes) != len(document.taxes):
        frappe.throw("Tax Template {} Data does not match with Document# {}'s Tax {}".
                     format(template.name,document.name, document.taxes_and_charges))
    if document.taxes:
        for tax in document.taxes:
            for temp in template.taxes:
                if tax.idx == temp.idx:
                    if tax.charge_type != temp.charge_type or tax.row_id != temp.row_id or tax.account_head != \
                            temp.account_head or tax.included_in_print_rate != temp.included_in_print_rate or tax.rate !=\
                            temp.rate:
                        frappe.throw(("Selected Tax {0}'s table does not match with tax table of Sales Order# {1}. Check "
                                      "Row # {2} or reload Taxes").format(document.taxes_and_charges, document.name,
                                                                          tax.idx))
    else:
        frappe.throw("Empty Tax Table is not Allowed for Sales Invoice {0}".format(document.name))


def check_dynamic_link(parenttype, parent, link_doctype, link_name):
    link_type = frappe.db.sql("""SELECT name FROM `tabDynamic Link`
        WHERE docstatus = 0 AND parenttype = '%s' AND parent = '%s'
        AND link_doctype = '%s' AND link_name = '%s'""" % (parenttype, parent, link_doctype, link_name), as_list=1)
    if not link_type:
        frappe.throw("{} {} does not belong to {} {}".format(parenttype, parent, link_doctype, link_name))


def replace_java_chars(string):
    replace_dict = {
        "false": "False",
        "true": "True",
        "&&": " and ",
        "||": " or ",
        "&gt;": ">",
        "&lt;": "<"
    }
    for k, v in replace_dict.items():
        string = string.replace(k, v)
    return string


def fn_check_digit(id_without_check):
    # This code generates the checkdigit for a given string
    # allowable characters within identifier
    valid_chars = "0123456789ABCDEFGHJKLMNPQRSTUVYWXZ"

    # remove leading or trailing whitespace, convert to uppercase
    id_without_checkdigit = id_without_check.strip().upper()

    # this will be a running total
    sum = 0

    # loop through digits from right to left
    for n, char in enumerate(reversed(id_without_checkdigit)):

        if not valid_chars.count(char):
            frappe.throw('Invalid Character has been used for Item Code check Attributes')

        # our "digit" is calculated using ASCII value - 48
        digit = ord(char) - 48

        # weight will be the current digit's contribution to
        # the running total
        weight = None
        if (n % 2 == 0):

            # for alternating digits starting with the rightmost, we
            # use our formula this is the same as multiplying x 2 &
            # adding digits together for values 0 to 9.  Using the
            # following formula allows us to gracefully calculate a
            # weight for non-numeric "digits" as well (from their
            # ASCII value - 48).
            weight = (2 * digit) - int((digit / 5)) * 9
        else:
            # even-positioned digits just contribute their ascii
            # value minus 48
            weight = digit

        # keep a running total of weights
        sum += weight

    # avoid sum less than 10 (if characters below "0" allowed,
    # this could happen)
    sum = abs(sum) + 10

    # check digit is amount needed to reach next number
    # divisible by ten. Return an integer
    return int((10 - (sum % 10)) % 10)


def fn_next_string(doc,s):
    #This function would increase the serial number by One following the
    #alpha-numeric rules as well
    if len(s) == 0:
        return '1'
    head = s[0:-1]
    tail = s[-1]
    if tail == 'Z':
        return fn_next_string(doc, head) + '0'
    if tail == '9':
        return head+'A'
    if tail == 'H':
        return head+'J'
    if tail == 'N':
        return head+'P'
    return head + chr(ord(tail)+1)
