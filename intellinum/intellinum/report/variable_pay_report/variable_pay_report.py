import frappe
from frappe.utils import getdate, today
from datetime import date

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "employee", "label": "Employee ID", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 220},
        {"fieldname": "percentage", "label": "Percentage (%)", "fieldtype": "Data", "width": 110},
        {"fieldname": "performance_remark", "label": "Performance Remark", "fieldtype": "Data", "width": 300},
        {"fieldname": "action", "label": "Action", "fieldtype": "Data", "width": 110},
    ]


def get_data(filters):
    if not filters.get("payroll_month"):
        filters["payroll_month"] = MONTH_NAMES[getdate().month - 1]

    conditions = [
        "`tabEmployee`.status = 'Active'",
        "IFNULL(`tabEmployee`.custom_quarter_variable, 0) > 0",
        "`tabEmployee`.custom_variable_pay_months LIKE %(month_like)s",
        "(`tabEmployee`.date_of_joining IS NULL OR NOT (YEAR(`tabEmployee`.date_of_joining) = %(current_year)s AND DATE_FORMAT(`tabEmployee`.date_of_joining, '%%b') = %(payroll_month)s))",
    ]

    user_roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in user_roles and "Administrator" not in user_roles:
        logged_in_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
        if logged_in_emp:
            conditions.append("`tabEmployee`.reports_to = %(reports_to)s")
            filters["reports_to"] = logged_in_emp
        else:
            conditions.append("1 = 0")

    if filters.get("company"):
        conditions.append("`tabEmployee`.company = %(company)s")
    if filters.get("department"):
        conditions.append("`tabEmployee`.department = %(department)s")

    filters["month_like"] = f"%{filters['payroll_month']}%"
    filters["current_year"] = getdate().year

    sql = f"""
        SELECT
            `tabEmployee`.name AS employee,
            `tabEmployee`.employee_name AS employee_name,
            `tabEmployee`.custom_quarter_variable AS quarter_variable,
            vpd.name AS vpd_name,
            vpd.percent AS approved_percent,
            vpd.comments AS performance_remark,
            vpd.variable_given AS variable_given,
            CASE
                WHEN vpd.name IS NOT NULL THEN 'Approved'
                ELSE 'Pending'
            END AS action
        FROM `tabEmployee`
        LEFT JOIN `tabVariable Pay Disbursement` vpd
            ON vpd.name = (
                SELECT vpd2.name
                FROM `tabVariable Pay Disbursement` vpd2
                WHERE vpd2.employee = `tabEmployee`.name
                  AND YEAR(vpd2.payroll_disburse_date) = %(current_year)s
                  AND DATE_FORMAT(vpd2.payroll_disburse_date, '%%b') = %(payroll_month)s
                  AND vpd2.docstatus = 1
                ORDER BY vpd2.creation DESC
                LIMIT 1
            )
        WHERE {" AND ".join(conditions)}
        ORDER BY `tabEmployee`.name
    """

    rows = frappe.db.sql(sql, filters, as_dict=True)

    data = []
    for row in rows:
        item = {
            "employee": row["employee"],
            "employee_name": row["employee_name"],
            "action": row["action"],
        }

        if row.get("vpd_name"):
            percent = row.get("approved_percent")
            if percent is None:
                base = float(row.get("quarter_variable") or 0)
                paid = float(row.get("variable_given") or 0)
                percent = round((paid / base) * 100) if base > 0 else 0

            item["percentage"] = str(int(round(float(percent or 0))))
            item["performance_remark"] = row.get("performance_remark") or "-"
        else:
            item["percentage"] = ""
            item["performance_remark"] = ""

        data.append(item)

    return data


@frappe.whitelist()
def process_single_approval(employee, percentage, performance_remark, company=None, payroll_month=None):
    if not employee:
        frappe.throw("Employee is required.")

    try:
        percentage = float(percentage)
    except Exception:
        frappe.throw("Percentage must be a valid number.")

    if percentage <= 0 or percentage > 100:
        frappe.throw("Percentage must be between 1 and 100.")

    if not performance_remark or not performance_remark.strip():
        frappe.throw("Performance Remark is mandatory.")

    emp = frappe.get_doc("Employee", employee)

    quarter_variable = float(emp.get("custom_quarter_variable") or 0)
    variable_full_year = float(emp.get("custom_variable_amount") or 0)

    if quarter_variable <= 0:
        frappe.throw("Quarter Variable is not configured in Employee master.")

    if variable_full_year <= 0:
        variable_full_year = quarter_variable * 4

    month_name = payroll_month or MONTH_NAMES[getdate().month - 1]

    try:
        month_index = MONTH_NAMES.index(month_name) + 1
    except ValueError:
        frappe.throw(f"Invalid payroll month: {month_name}")

    payroll_date = date(getdate().year, month_index, 1)

    existing_vpd = frappe.db.sql(
        """
        SELECT name
        FROM `tabVariable Pay Disbursement`
        WHERE employee = %s
          AND YEAR(payroll_disburse_date) = %s
          AND MONTH(payroll_disburse_date) = %s
          AND docstatus = 1
        LIMIT 1
        """,
        (employee, payroll_date.year, payroll_date.month),
        as_dict=True,
    )

    if existing_vpd:
        frappe.throw(f"Variable Pay already approved for {emp.employee_name} in {month_name}.")

    vpd = frappe.get_doc({
        "doctype": "Variable Pay Disbursement",
        "employee": employee,
        "employee_name": emp.employee_name,
        "variable_full_year": variable_full_year,
        "quarter_variable": quarter_variable,
        "percent": percentage,
        "comments": performance_remark.strip(),
        "disburse_date": today(),
        "payroll_disburse_date": payroll_date,
    })

    vpd.insert(ignore_permissions=True)
    vpd.submit()

    return {
        "message": "Success",
        "vpd": vpd.name,
    }