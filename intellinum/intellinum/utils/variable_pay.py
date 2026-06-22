import frappe
from frappe.utils import getdate, today
from datetime import date

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _original_submission_count(employee):
    return frappe.db.sql(
        """
        SELECT COUNT(*)
        FROM `tabVariable Pay Disbursement`
        WHERE employee = %s
          AND docstatus = 1
          AND IFNULL(amended_from, '') = ''
        """,
        (employee,),
    )[0][0]


def _employee_company(employee):
    return frappe.db.get_value("Employee", employee, "company")


def before_save(doc, method=None):
    """
    Validation + computed fields before saving VPD.
    """
    if not doc.employee:
        frappe.throw("Employee is required.")

    if not doc.employee_name:
        doc.employee_name = frappe.db.get_value("Employee", doc.employee, "employee_name") or ""

    # Fill variable_full_year if missing.
    # Employee has custom_variable_amount, so use that first.
    if not doc.variable_full_year or float(doc.variable_full_year or 0) <= 0:
        emp_variable_amount = float(
            frappe.db.get_value("Employee", doc.employee, "custom_variable_amount") or 0
        )
        if emp_variable_amount > 0:
            doc.variable_full_year = emp_variable_amount
        else:
            doc.variable_full_year = float(doc.quarter_variable or 0) * 4

    if float(doc.quarter_variable or 0) <= 0:
        frappe.throw("Quarter Variable is not configured in Employee master.")

    # Compute payout
    if float(doc.quarter_variable or 0) > 0 and float(doc.percent or 0) > 0:
        doc.variable_given = (float(doc.quarter_variable or 0) * float(doc.percent or 0)) / 100

    # Require a reason when amending/revising
    if doc.amended_from and not (doc.override_reason or "").strip():
        frappe.throw("Override Reason is required when amending Variable Pay Disbursement.")


def on_submit(doc, method=None):
    existing_ads = frappe.db.get_value(
        "Additional Salary",
        {
            "custom_variable_pay_disbursement": doc.name,
            "docstatus": ["!=", 2],
        },
        "name",
    )

    if existing_ads:
        return

    company = _employee_company(doc.employee)
    if not company:
        frappe.throw(f"Company is not set for employee {doc.employee}.")

    employee_name = frappe.db.get_value("Employee", doc.employee, "employee_name") or ""

    ads_data = {
        "doctype": "Additional Salary",
        "employee": doc.employee,
        "company": company,
        "payroll_date": doc.payroll_disburse_date or today(),
        "salary_component": "Variable Pay",
        "amount": float(doc.variable_given or 0),
    }

    ads_meta = frappe.get_meta("Additional Salary")

    if ads_meta.has_field("employee_name"):
        ads_data["employee_name"] = employee_name

    if ads_meta.has_field("custom_variable_pay_disbursement"):
        ads_data["custom_variable_pay_disbursement"] = doc.name

    if ads_meta.has_field("type"):
        ads_data["type"] = "Earning"

    ads = frappe.get_doc(ads_data)
    ads.insert(ignore_permissions=True, ignore_links=True)
    ads.submit()

def on_cancel(doc, method=None):
    """
    Cancel linked Additional Salary when VPD is cancelled.
    """
    ads_name = frappe.db.get_value(
        "Additional Salary",
        {
            "custom_variable_pay_disbursement": doc.name,
            "docstatus": 1,
        },
        "name",
    )

    if ads_name:
        ads = frappe.get_doc("Additional Salary", ads_name)
        ads.cancel()