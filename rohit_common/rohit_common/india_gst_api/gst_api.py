#  Copyright (c) 2022. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
# -*- coding: utf-8 -*-
import datetime
import frappe
import requests
from frappe.utils import flt
from .common import get_gsp_details, get_api_version
TIMEOUT = 7


def get_gstr1(gstin, ret_period, action):
    """
    Returns JSON for GSTR1 for a given GSTIN, Return Period and action is Required
    Action is basically Sub-type like B2B etc for Returns
    """
    api = "gstr1"
    auth_token = get_auth_token(gstin)
    url = get_gst_url(api, action, gstin) + "&authtoken=" + auth_token + "&ret_period=" + ret_period
    resp = get_gst_response(url=url, type_of_req="get")
    if flt(resp.get("status_cd")) == 1:
        pass
    elif resp.get(action.lower(), None) is not None:
        pass
    elif flt(resp.get("status_cd")) == 0:
        resp = []
    else:
        frappe.throw(f"Some Error in Response with Error Message = {resp} URL Used= {url}")
    return resp


def get_gstr2a(gstin, ret_period, action):
    """
    Returs JSON for GSTR2A for a GSTIN, Return Period and Action is also required
    Action is basically Sub-type like B2B etc for Returns
    """
    api = "gstr2a"
    auth_token = get_auth_token(gstin)
    url = get_gst_url(api, action, gstin) + "&authtoken=" + auth_token + "&ret_period=" + ret_period
    resp = get_gst_response(url=url, type_of_req="get")
    if flt(resp.get("status_cd")) == 1:
        pass
    elif resp.get(action.lower(), None) is not None:
        pass
    elif flt(resp.get("status_cd")) == 0:
        resp = []
    else:
        frappe.throw(f"Some Error in Response with Error Message = {resp} URL Used= {url}")
    return resp


def get_gstr2b(gstin, ret_period, action, file_num=None):
    """
    Returns JSON for GSTR2B for GSTIN, Return Period and Action is Required.
    Action is basically Sub-type like B2B etc for Returns
    """
    if file_num:
        file_num_link = "&file_num" + file_num
    else:
        file_num_link = ""
    api = "gstr2b"
    auth_token = get_auth_token(gstin)
    url = get_gst_url(api, action, gstin) + "&authtoken=" + auth_token + "&rtnprd=" + ret_period + \
        "&ret_period=" + ret_period + file_num_link
    resp = get_gst_response(url=url, type_of_req="get")
    if resp.get("chksum"):
        pass
    else:
        frappe.throw(f"Some Error in Response with Error Message = {resp} URL Used= {url}")
    return resp


def get_gst_response(url, type_of_req):
    """
    Based on Type of Request it would do a post or get request for a URL given
    """
    if type_of_req == "post":
        response = requests.post(url=url, timeout=TIMEOUT).json()
    elif type_of_req == "get":
        response = requests.get(url=url, timeout=TIMEOUT).json()
    else:
        frappe.throw(f"Type of Request {type_of_req} is Not Defined")
    return response


@frappe.whitelist()
def get_gst_otp(gstin):
    """
    Send a request to GST server to send OTP to registered mobile number of a given GST
    """
    api = "otp"
    action = "OTPREQUEST"
    otp_url = get_gst_url(api=api, action=action, gstin=gstin)
    res = requests.get(otp_url, timeout=TIMEOUT).json()
    if flt(res.get("status_cd")) == 1:
        frappe.msgprint("OTP Sent Successfully, Please enter the OTP sent to RMN")
    else:
        frappe.msgprint(f"OTP Generation Failed. Please try again later. Error Message is {res} \
            and OTP URL {otp_url}")


@frappe.whitelist()
def authenticate_gst_otp(gstin, otp, row_id):
    """
    To authenticate the OTP received on RMN this is used
    """
    api = "otp"
    action = "AUTHTOKEN"
    auth_url = get_gst_url(api=api, action=action, gstin=gstin) + "&OTP=" + otp
    auth_resp = requests.get(url=auth_url, timeout=TIMEOUT)
    auth_resp = auth_resp.json()
    if flt(auth_resp.get("status_cd")) == 1:
        frappe.db.set_value("GST Registration Details", row_id, "last_otp_sent",
                datetime.datetime.now())
        update_auth_token(row_name=row_id, auth_token=auth_resp.get("auth_token"))
        frappe.msgprint(f"Updated the Auth Token. Now API access to {gstin} is Active")
    else:
        update_auth_token(row_name=row_id, auth_token="", failed=1)
        frappe.throw(f"OTP Validation Failed and Error Message = {auth_resp} and Link = {auth_url}")


def check_for_refresh_token(row):
    """
    For a row dict would check if the Auth Token is needed to be refreshed for a GSTIN
    """
    now_time = datetime.datetime.now()
    token_time = flt(row.update_token_every_mins)
    if row.authorization_token and row.api_access_authorized == 1:
        token_update_time = row.validity_of_token - datetime.timedelta(minutes=360) + \
            datetime.timedelta(minutes=token_time)
        if token_update_time < now_time < row.validity_of_token:
            new_auth_token, error_code = refresh_auth_token(row.gst_registration_number,
                row.authorization_token)
            if new_auth_token != "":
                print(f"Auto Updated Auth Token for {row.gst_registration_number}")
                update_auth_token(row_name=row.name, auth_token=new_auth_token)
            else:
                print(f"Auto Auth Token Update Failed for {row.gst_registration_number}")
                update_auth_token(row_name=row.name, auth_token="", failed=1, error_code=error_code)
        elif token_update_time > now_time and row.validity_of_token > now_time:
            print(f"No Need to Update the Auth Token for {row.gst_registration_number} as Token to \
                be Updated After {token_update_time}")
        else:
            print(f"Auth Token is Expired and hence Need to Generate OTP Again for \
                {row.gst_registration_number}")
            update_auth_token(row_name=row.name, auth_token="", failed=1, error_code='AUTH4037')
    elif row.api_access_authorized != 1:
        print(f"API Authorization is Unchecked for {row.gst_registration_number}")
    else:
        print(f"No API Authorization Token for {row.gst_registration_number}")


def refresh_auth_token(gstin, auth_token):
    """
    Tries to refresh the auth token for a given GSTIN and Auth Token
    """
    error_code = ""
    api = "otp"
    action = "REFRESHTOKEN"
    ref_url = get_gst_url(api=api, action=action, gstin=gstin) + "&AuthToken=" + auth_token
    ref_resp = requests.get(url=ref_url, timeout=TIMEOUT).json()
    if flt(ref_resp.get("status_cd")) == 1:
        refresh_resp = ref_resp.get("auth_token")
    else:
        refresh_resp = ""
        error = ref_resp.get('error')
        print(f"Some Error in Refreshing the Auth Token with Error = {ref_resp.get('error')} and \
            URL being used = {ref_url} and full response is {ref_resp}")
        error_code = error.get("error_cd")
    return refresh_resp, error_code


def get_auth_token(gstin):
    """
    Gets auth token for a given GSTIN
    """
    found = 0
    r_set = frappe.get_doc("Rohit GST Settings", "Rohit GST Settings")
    now_time = datetime.datetime.now()
    new_auth_token = ""
    for row in r_set.gst_registration_details:
        if row.gst_registration_number == gstin:
            # Updates token after this many mins
            token_update_min = flt(row.update_token_every_mins)
            token_update_time = row.validity_of_token - datetime.timedelta(minutes=360) + \
                datetime.timedelta(minutes=token_update_min)
            found = 1
            if row.authorization_token and row.api_access_authorized == 1:
                if token_update_time > now_time and row.validity_of_token > now_time:
                    new_auth_token = row.authorization_token
                elif token_update_time < now_time < row.validity_of_token:
                    new_auth_token, error_code = refresh_auth_token(gstin=gstin,
                        auth_token=row.authorization_token)
                    if new_auth_token != "":
                        update_auth_token(row_name=row.name, auth_token=new_auth_token,
                            error_code=error_code)
                    else:
                        update_auth_token(row_name=row.name, auth_token="", failed=1,
                            error_code=error_code)
                        frappe.throw(f"New Auth Token for {gstin} is Empty you might need to \
                            Generate OTP Again")
                else:
                    update_auth_token(row_name=row.name, auth_token="", failed=1,
                        error_code="AUTH4037")
                    frappe.throw(f"Auth Token for {gstin} is Expired you might need to \
                        Generate OTP Again")
            else:
                frappe.throw(f"Authorization Needed for {gstin}. Resend OTP and Get Authorization")
    if found == 0:
        frappe.throw(f"{gstin} is Not Setup in Rohit GST Settings for API Access")
    return new_auth_token


def update_auth_token(row_name, auth_token, failed=0, error_code=None):
    """
    Updates the Auth Token for a Row Name in the GST Registration Details
    """
    if not error_code:
        error_code = ""
    ecl = ["AUTH4037", "RET11402", "SWEB9033", "AUTH4033", "GSP102"]
    if failed == 1:
        # Only Update API Access to zero on certain errors and not all errors
        frappe.db.set_value("GST Registration Details", row_name, "otp", "")
        if error_code != "" and error_code in ecl:
            print("Removing API Access")
            frappe.db.set_value("GST Registration Details", row_name, "api_access_authorized", 0)
        else:
            print(f"Error Code: {str(error_code)} Not in List")
        frappe.db.commit()
    else:
        auth_access = flt(frappe.db.get_value("GST Registration Details", row_name,
            "api_access_authorized"))
        exist_token_times = flt(frappe.db.get_value("GST Registration Details", row_name,
            "no_of_times_token_updated"))
        if auth_access == 1:
            frappe.db.set_value("GST Registration Details", row_name, "no_of_times_token_updated",
                exist_token_times + 1)
        else:
            frappe.db.set_value("GST Registration Details", row_name, "no_of_times_token_updated",
                0)
        frappe.db.set_value("GST Registration Details", row_name, "api_access_authorized", 1)
        frappe.db.set_value("GST Registration Details", row_name, "authorization_token", auth_token)
        frappe.db.set_value("GST Registration Details", row_name, "otp", "")
        frappe.db.set_value("GST Registration Details", row_name, "validity_of_token",
                            datetime.datetime.now() + datetime.timedelta(minutes=360))


def get_gst_url(api, action, gstin):
    """
    Gets the URL for a GSTIN api, action and GSTIN
    """
    gsp_link, asp_id, asp_pass, gstin_other, sandbox = get_gsp_details(api=api, action=action)
    username = get_gst_username(gstin=gstin)
    version, act_type = get_api_version(api)
    gst_url = gsp_link + "/taxpayerapi/dec/" + version + "/" + act_type + "?action=" + action + \
        "&aspid=" + asp_id + "&password=" + asp_pass + "&gstin=" + gstin + "&username=" + username
    return gst_url


def get_gst_username(gstin):
    """
    Get the GST Username from Rohit GST Settings for a given GSTIN
    """
    found = 0
    gst_username = ""
    r_set = frappe.get_doc("Rohit GST Settings", "Rohit GST Settings")
    for row in r_set.gst_registration_details:
        if row.gst_registration_number == gstin:
            found = 1
            gst_username = row.gst_username
    if found == 0:
        frappe.throw(f"No GSTIN username found for {gstin}")
    return gst_username


def get_invoice_type(itype):
    """
    Returns the Invoice Type for a Invoice Type code
    """
    inv_type_txt = ""
    if itype == "R":
        inv_type_txt = "R-Regular B2B Invoices"
    elif itype == "DE":
        inv_type_txt = "DE-Deemed Exports"
    elif itype == "SEWP":
        inv_type_txt = "SEWP-SEZ Exports with payment"
    elif itype == "SEWOP":
        inv_type_txt = "SEWOP-SEZ exports without payment"
    return inv_type_txt


def get_type_of_amend(amend_type):
    """
    Returns text for a the Type of Amend to the Invoice for a Code
    """
    amd_type_txt = ""
    if amend_type == "R":
        amd_type_txt = "R-Receiver GSTIN Amended"
    elif amend_type == "N":
        amd_type_txt = "N-Invoice Number Amended"
    elif amend_type == "D":
        amd_type_txt = "D-Details Amended"
    return amd_type_txt
