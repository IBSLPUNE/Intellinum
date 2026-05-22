# # Copyright (c) 2026, ibsl and contributors
# # For license information, please see license.txt
#
# # import frappe
#
#
# # def execute(filters=None):
# # 	columns, data = [], []
# # 	return columns, data



# Copyright (c) 2026, ibsl and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"label": _("Employee"),                        "fieldname": "employee",                        "fieldtype": "Link", "options": "Employee", "width": 100},
        {"label": _("Employee Name"),                   "fieldname": "employee_name",                   "fieldtype": "Data",  "width": 220},
        {"label": _("Employment Type"),                 "fieldname": "employment_type",                 "fieldtype": "Data",  "width": 130},
        {"label": _("Date of Joining"),                 "fieldname": "date_of_joining",                 "fieldtype": "Date",  "width": 120},
        {"label": _("Confirmation Date"),               "fieldname": "final_confirmation_date",         "fieldtype": "Date",  "width": 140},
        {"label": _("Annual Leave"),                    "fieldname": "annual_leave",                    "fieldtype": "Float", "width": 110},
        {"label": _("Leave to be Allocated"),           "fieldname": "leave_to_be_allocated",           "fieldtype": "Float", "width": 160},
        {"label": _("Optional Holidays"),               "fieldname": "optional_holidays",               "fieldtype": "Float", "width": 130},
        {"label": _("Optional Holidays to Allocate"),   "fieldname": "optional_holidays_to_allocate",   "fieldtype": "Float", "width": 190},
        {"label": _("Status"),                          "fieldname": "status",                          "fieldtype": "Data",  "width": 110},
        {"label": _("Action"),                          "fieldname": "action",                          "fieldtype": "Data",  "width": 130},
    ]

def get_data(filters):
    conditions = "WHERE e.final_confirmation_date IS NOT NULL AND e.status = 'Active'"
    if filters:
        if filters.get("from_date"):
            conditions += " AND e.final_confirmation_date >= %(from_date)s"
        if filters.get("to_date"):
            conditions += " AND e.final_confirmation_date <= %(to_date)s"

    data = frappe.db.sql(
        """
        SELECT
            e.name AS employee,
            e.employee_name,
            e.employment_type,
            e.date_of_joining,
            e.final_confirmation_date,
            21.0 AS annual_leave,
            LEAST(
                ROUND(
                    (DATEDIFF(CONCAT(YEAR(CURDATE()), '-12-31'), e.final_confirmation_date) + 1)
                    / 365.0 * 21,
                    2
                ),
                21.0
            ) AS leave_to_be_allocated,
            4.0 AS optional_holidays,
            LEAST(
                ROUND(
                    (DATEDIFF(
                        CONCAT(YEAR(CURDATE()), '-12-31'),
                        CASE
                            WHEN YEAR(e.date_of_joining) = YEAR(CURDATE())
                                THEN e.date_of_joining
                            ELSE CONCAT(YEAR(CURDATE()), '-01-01')
                        END
                    ) + 1)
                    / 365.0 * 4,
                    2
                ),
                4.0
            ) AS optional_holidays_to_allocate,
            CASE
                WHEN la.name IS NOT NULL THEN 'Allocated'
                ELSE 'Pending'
            END AS status,
            la.name AS allocation_name
        FROM `tabEmployee` e
        LEFT JOIN `tabLeave Allocation` la
            ON  la.employee   = e.name
            AND la.leave_type = 'Paid Leave'
            AND la.docstatus  = 1
            AND YEAR(la.to_date) = YEAR(CURDATE())
        {conditions}
        ORDER BY e.name
        """.format(conditions=conditions),
        filters or {},
        as_dict=True,
    )

    for row in data:
        row["action"] = "Allocate" if row.get("status") == "Pending" else ""

    return data
