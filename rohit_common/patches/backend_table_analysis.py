#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
import math
import frappe
import time
from frappe.utils import flt
from frappe.model import no_value_fields, default_fields, numeric_fieldtypes, optional_fields


def find_unused_fields():
    sno = 0
    tb = input_table_name()
    st_time = time.time()
    all_fields_db = get_all_fields_in_tbl(tb_name=tb)
    std_doc_fds = get_all_std_fields(tb_name=tb, field_types=1)
    for fd in all_fields_db:
        max_len = frappe.db.sql("""SELECT MAX(LENGTH(%s)) AS max_size FROM `tab%s`""" % (fd.column_name, tb), as_dict=1)
        if flt(max_len[0].max_size) == 0:
            sno += 1
            print(f"{sno}. Field Name = {fd.column_name} with Data Type = {fd.data_type} but Does not Have any Data")
    print(f"Total Time Taken = {int(time.time() - st_time)} seconds and Total Fields = {len(all_fields_db)} and "
          f"Total Fields without Data = {sno}")


def get_all_std_fields(tb_name, field_types=2):
    # field_type (0 for No Value Fields, 1 for Non-No Value fields, 2 for All fields)
    cond, val = "", ""
    if field_types != 2:
        cond += " AND fieldtype %s IN %s" % (val, no_value_fields)
    if field_types == 1:
        val = "NOT"

    doc_fields = frappe.db.sql("""SELECT name, fieldname, fieldtype, idx FROM `tabDocField` 
    WHERE parent = '%s' AND parenttype = 'DocType' %s
    ORDER BY idx""" % (tb_name, cond), as_dict=1)
    return doc_fields


def get_all_fields_in_tbl(tb_name):
    all_fds_dict = frappe.db.sql("""SELECT column_name, data_type, character_maximum_length 
    FROM information_schema.columns WHERE table_name = 'tab%s'""" % tb_name, as_dict=1)
    return all_fds_dict


def input_table_name():
    tb = input("Enter the Name of the Table for Dropping Fields Ex: Sales Invoice, enter the value exactly as in ERP: ")
    tbl_exists = frappe.db.sql("""SHOW TABLES LIKE 'tab%s'""" % tb)
    if not tbl_exists:
        print(f"There is No Table Named tab{tb}. Hence Exiting")
        exit()
    else:
        return tb


def drop_redundant_fields():
    tb = input_table_name()
    st_time = time.time()
    not_fields_list = []
    all_fields_act = []
    not_found_fields = 0
    all_fields_db = get_all_fields_in_tbl(tb_name=tb)

    doc_fields = frappe.db.sql("""SELECT name, fieldname, fieldtype, idx FROM `tabDocField` 
    WHERE parent = '%s' AND parenttype = 'DocType' AND fieldtype NOT IN %s
    ORDER BY idx""" % (tb, no_value_fields), as_dict=1)

    cu_fd = frappe.db.sql("""SELECT name, fieldname, fieldtype, idx FROM `tabCustom Field` 
    WHERE dt = '%s'
    ORDER BY idx""" % tb, as_dict=1)

    for fd in default_fields:
        if fd != 'doctype':
            all_fields_act.append(fd)

    for fd in optional_fields:
        all_fields_act.append(fd)

    for fd in doc_fields:
        all_fields_act.append(fd.fieldname)

    for fd in cu_fd:
        all_fields_act.append(fd.fieldname)

    # Check if fields in DB are in actual fields in Custom fields and actual fields
    for fd in all_fields_db:
        if fd.column_name not in all_fields_act:
            # These fields can be dropped but like TiN no and Excise Nos should be kept
            not_found_fields += 1
            not_fields_list.append(fd.column_name)
    print(f"Total Obsolete Fields in {tb} = {not_found_fields} and they are \n {not_fields_list}")
    input("Press Any Key to Continue With Deletion of these Redundant Fields...")
    query = f"ALTER TABLE `tab{tb}` " + ", ".join(["DROP COLUMN `%s`" % f for f in not_fields_list])
    frappe.db.sql(query)
    print(f"Total Time Taken = {int(time.time() - st_time)} secs to DROP {len(not_fields_list)} Fields from {tb} Table")


def reduce_varchar_size():
    tb = input_table_name()
    fields_to_check = []
    doc_fields = frappe.db.sql("""SELECT name, fieldname, fieldtype, idx FROM `tabDocField` 
    WHERE parent = '%s' AND parenttype = 'DocType' AND fieldtype NOT IN %s
    ORDER BY idx""" % (tb, no_value_fields), as_dict=1)

    cu_fd = frappe.db.sql("""SELECT name, fieldname, fieldtype, idx FROM `tabCustom Field` 
    WHERE dt = '%s' AND fieldtype NOT IN %s
    ORDER BY idx""" % (tb, no_value_fields), as_dict=1)

    for fd in default_fields:
        field_dict = frappe._dict({})
        field_dict["fieldname"] = fd
        field_dict["idx"] = 0

        if fd != 'doctype':
            fields_to_check.append(field_dict)

    for fd in optional_fields:
        field_dict = frappe._dict({})
        field_dict["fieldname"] = fd
        field_dict["idx"] = 0

    for fd in doc_fields:
        if fd.fieldtype not in numeric_fieldtypes and fd.fieldtype != 'Date':
            fields_to_check.append(fd)

    for fd in cu_fd:
        if fd.fieldtype not in numeric_fieldtypes and fd.fieldtype != 'Date':
            fields_to_check.append(fd)

    fields_to_check = sorted(fields_to_check, key=lambda i: (i["idx"], i["fieldname"]))
    for fd in fields_to_check:
        fd_size = frappe.db.sql("""SELECT table_name AS tbl, column_name AS col, column_type AS col_type, 
        data_type AS dt_type, character_maximum_length AS char_len 
        FROM information_schema.columns WHERE column_name = '%s' 
        AND table_name = 'tab%s'""" % (fd.fieldname, tb), as_dict=1)
        if fd_size:
            max_size = frappe.db.sql("""SELECT MAX(LENGTH(%s)) AS max_size 
            FROM `tab%s`""" % (fd.fieldname, tb), as_dict=1)
            fd_size[0]["max_size"] = max_size[0].max_size
        if fd_size[0].dt_type == 'varchar':
            if flt(fd_size[0].max_size) > 0:
                new_size = int(math.ceil(fd_size[0].max_size * 2 / 10)) * 10
                if new_size >= 0.9 * fd_size[0].char_len:
                    new_size = fd_size[0].char_len
            else:
                new_size = 70
            if fd_size[0].col in default_fields and new_size != fd_size[0].char_len:
                # Default fields would be changed automatically to double the max length
                fd_time = time.time()
                # Change the size to new size
                alter_varchar_table(tb_name=tb, col_name=fd_size[0].col, var_len=new_size)
                print(f"Changed {fd_size[0].col} from Size = {fd_size[0].char_len} to New Size= {new_size} \n"
                      f"Time Taken for Field Conversion = {int(time.time() - fd_time)} seconds and Total Elapsed "
                      f"Time = {int(time.time() - st_time)} seconds")
            else:
                # Suggestion for Customize Form View or Change here only based on User input
                # Input would be of 2 types 1 for Yes and then also a manual value can be added for length
                # which should be higher than the max_length and lower 1000
                if new_size == fd_size[0].char_len:
                    print(f"{fd_size[0].col} No Change Needed As Current Size = {fd_size[0].char_len}")
                    change_here = get_input_for_change(exist_len=fd_size[0].char_len, max_len=fd_size[0].max_size,
                                                       sug_len=new_size, limit=1000, col_name=fd_size[0].col)
                    change_varchar_len_as_per_input(tbl_name=tb, col_name=fd_size[0].col, exist_len=fd_size[0].char_len,
                                                    max_len=fd_size[0].max_size, sug_len=new_size, st_time=st_time,
                                                    usr_inp=change_here)
                else:
                    print(f"{fd_size[0].col} Old Size= {fd_size[0].char_len} "
                          f"Max Length in DB = {fd_size[0].max_size} "
                          f"Suggested Value for New Size = {new_size}\n")
                    change_here = get_input_for_change(exist_len=fd_size[0].char_len, max_len=fd_size[0].max_size,
                                                       sug_len=new_size, limit=1000, col_name=fd_size[0].col)
                    change_varchar_len_as_per_input(tbl_name=tb, col_name=fd_size[0].col, exist_len=fd_size[0].char_len,
                                                    max_len=fd_size[0].max_size, sug_len=new_size, st_time=st_time,
                                                    usr_inp=change_here)

    std_fields = len(doc_fields) + len(default_fields) - 1
    cust_fields = len(cu_fd)
    tot_fileds = std_fields + cust_fields
    print(f"Total Standard Fields found in Table {tb} = {std_fields} \n"
          f"Total Custom fields found in Table {tb} = {cust_fields} Total = {tot_fileds}")
    print(f"Total Fields to be Checked = {len(fields_to_check)}")
    print(f"Total Time Taken = {int(time.time() - st_time)} seconds")


def change_varchar_len_as_per_input(tbl_name, col_name, exist_len, max_len, sug_len, st_time, usr_inp=None):
    if not usr_inp:
        fd_time = time.time()
        # Apply the suggested size here
        alter_varchar_table(tb_name=tbl_name, col_name=col_name, var_len=sug_len)
        print(f"Changed {col_name} from Size = {exist_len} to New Size= {sug_len} \n"
              f"Time Taken for Field Conversion = {int(time.time() - fd_time)} secs and Total Elapsed "
              f"Time = {int(time.time() - st_time)} secs\n")
    elif usr_inp == 'N':
        # Changes would be done manually in Customize Form View by user
        pass
    elif flt(max_len) <= int(usr_inp) < 1000:
        fd_time = time.time()
        # Apply the change_here value to new varchar
        alter_varchar_table(tb_name=tbl_name, col_name=col_name, var_len=int(usr_inp))
        print(f"Changed {col_name} from Size = {exist_len} to New Size= {usr_inp} \n"
              f"Time Taken for Field Conversion = {int(time.time() - fd_time)} secs and Total Elapsed "
              f"Time = {int(time.time() - st_time)} secs\n")
    else:
        print(f"{usr_inp} is an Illegal Value please Restart again")
        exit()


def alter_varchar_table(tb_name, col_name, var_len):
    frappe.db.sql_ddl("""ALTER TABLE `tab%s` MODIFY COLUMN %s VARCHAR (%s)""" % (tb_name, col_name, var_len))


def get_input_for_change(col_name, exist_len, max_len, sug_len, limit):
    timeout = 3
    message = f"Do You Want to Change {col_name} Size. Current Length = {exist_len}, Max = {max_len} and " \
              f"Suggested = {sug_len}.\nEnter 'N' for No-Change, Enter Integer Value b/w {max_len} and {limit} or " \
              f"Just HIT Enter to Change Length to {sug_len}: "
    change_here = input(message)

    return change_here


def get_size_of_all_tables():
    config = frappe.get_site_config()
    query = """SELECT table_schema AS db_name, table_name AS tbl_name, 
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb, ROUND(((data_length) / 1024 / 1024), 2) AS dl_mb,
    ROUND(((index_length) / 1024 / 1024), 2) AS ind_mb, TABLE_ROWS as tbl_rows
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = '%s'
    ORDER BY (data_length + index_length) DESC""" % config.db_name
    data = frappe.db.sql(query, as_dict=1)
    return data


def get_columns_of_all_tables():
    config = frappe.get_site_config()
    query = """SELECT table_schema AS db_name, table_name AS tbl_name, COUNT(*) AS no_of_cols 
    FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema = '%s' GROUP BY tbl_name ORDER BY no_of_cols DESC;""" % config.db_name
    data = frappe.db.sql(query, as_dict=1)
    return data
