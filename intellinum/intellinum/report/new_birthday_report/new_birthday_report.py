import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 220
        },
        {
            "label": _("Date of Joining"),
            "fieldname": "date_of_joining",
            "fieldtype": "Date",
            "width": 130
        },
        {
            "label": _("Date of Birth"),
            "fieldname": "date_of_birth",
            "fieldtype": "Date",
            "width": 130
        },
        {
            "label": _("Confirmation Date"),
            "fieldname": "final_confirmation_date",
            "fieldtype": "Date",
            "width": 150
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Branch"),
            "fieldname": "branch",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("Department"),
            "fieldname": "department",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": _("Designation"),
            "fieldname": "designation",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": _("Gender"),
            "fieldname": "gender",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Data",
            "width": 220
        }
    ]


def get_data(filters):
    conditions = ""

    if filters.get("month"):
        month_map = {
            "Jan": 1,
            "Feb": 2,
            "Mar": 3,
            "Apr": 4,
            "May": 5,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Oct": 10,
            "Nov": 11,
            "Dec": 12
        }

        month_number = month_map.get(filters.get("month"))

        conditions += f" AND MONTH(date_of_birth) = {month_number}"

    if filters.get("company"):
        conditions += " AND company = %(company)s"

    if filters.get("employment_type"):
        conditions += " AND employment_type = %(employment_type)s"

    data = frappe.db.sql(f"""
        SELECT
            employee,
            employee_name,
            date_of_joining,
            date_of_birth,
            final_confirmation_date,
            status,
            branch,
            department,
            designation,
            gender,
            company
        FROM `tabEmployee`
        WHERE
            date_of_birth IS NOT NULL
            AND status != 'Left'
            {conditions}
        ORDER BY
            MONTH(date_of_birth),
            DAY(date_of_birth)
    """, filters, as_dict=1)

    return data