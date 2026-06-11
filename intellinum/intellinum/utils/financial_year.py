import frappe
from frappe.utils import getdate

def get_financial_year(date_value):
    if not date_value:
        return ""

    dt = getdate(date_value)
    start_year = dt.year if dt.month >= 4 else dt.year - 1
    end_year = start_year + 1
    return f"{start_year}-{str(end_year)[2:]}"


def set_vpd_financial_year(doc, method=None):
    doc.financial_year = get_financial_year(doc.payroll_disburse_date)


def set_additional_salary_financial_year(doc, method=None):
    doc.financial_year = get_financial_year(doc.payroll_date)


def set_salary_slip_financial_year(doc, method=None):
    # Use end_date as the payroll period reference
    doc.financial_year = get_financial_year(doc.end_date)