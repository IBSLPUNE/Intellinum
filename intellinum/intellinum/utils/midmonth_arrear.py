import frappe
from frappe.utils import flt, getdate, get_last_day, date_diff

COMPONENTS = [
    "Basic",
    "House Rent Allowance",
    "Special Allowance",
    "Other Allowance",
]

LOP_LEAVE_TYPE = "Leave Without Pay"

MONTHLY_TRANSPORT = 1600
MONTHLY_TELEPHONE = 2000
MONTHLY_INTERNET = 1800
MONTHLY_EDUCATION = 1250
MONTHLY_LTA = 2083
MONTHLY_MEDICAL = 1250

ANNUAL_PF_FOR_FORMULA = 21600

FIXED_ALLOWANCES = (
    MONTHLY_TRANSPORT
    + MONTHLY_TELEPHONE
    + MONTHLY_INTERNET
    + MONTHLY_EDUCATION
    + MONTHLY_LTA
    + MONTHLY_MEDICAL
)


def _month_start(date_value):
    return date_value.replace(day=1)


def _shift_year(date_value, years=1):
    try:
        return date_value.replace(year=date_value.year + years)
    except ValueError:
        return date_value.replace(year=date_value.year + years, month=2, day=28)


def _get_employee(employee):
    return frappe.db.get_value(
        "Employee",
        employee,
        ["employee_name", "company", "custom_effective_increment_date"],
        as_dict=True,
    )


def _get_applicable_ssa(employee, as_of_date, mode="previous"):
    filters = {
        "employee": employee,
        "docstatus": 1,
        "from_date": ["<", as_of_date] if mode == "previous" else [">=", as_of_date],
    }

    rows = frappe.get_all(
        "Salary Structure Assignment",
        filters=filters,
        fields=["name", "from_date"],
        order_by="from_date desc, creation desc" if mode == "previous" else "from_date asc, creation asc",
        limit=1,
    )

    return rows[0]["name"] if rows else None


def _get_ctc_from_ssa(ssa_name):
    ssa = frappe.get_doc("Salary Structure Assignment", ssa_name)
    return flt(
        ssa.get("custom_base_after_variable_pay")
        # or ssa.get("custom_ctc_cost_to_company")
        or 0
    )


def _calculate_breakup(ctc):
    monthly_ctc = flt(ctc) / 12
    basic = monthly_ctc * 0.4
    hra = (basic * 0.5)

    common_deductions = (
        basic
        + hra
        + MONTHLY_TRANSPORT
        + MONTHLY_TELEPHONE
        + MONTHLY_INTERNET
        + MONTHLY_EDUCATION
        + MONTHLY_LTA
        + MONTHLY_MEDICAL
    )

    special = (
        (
            ((flt(ctc) - hra - ANNUAL_PF_FOR_FORMULA) / 12)
            - common_deductions
        ) * 0.4
    )

    other = (
        (
            ((flt(ctc) - ANNUAL_PF_FOR_FORMULA - hra) / 12)
            - common_deductions
        ) * 0.6
    )

    return {
        "Basic": round(basic, 2),
        "House Rent Allowance": round(hra, 2),
        "Special Allowance": round(special, 2),
        "Other Allowance": round(other, 2),
    }


def _get_lop_days(employee, period_start, period_end):
    leave_apps = frappe.get_all(
        "Leave Application",
        filters={
            "employee": employee,
            "leave_type": LOP_LEAVE_TYPE,
            "docstatus": 1,
            "status": "Approved",
            "from_date": ["<=", period_end],
            "to_date": [">=", period_start],
        },
        fields=["name", "from_date", "to_date", "half_day", "half_day_date"],
    )

    lop_days = 0.0

    for app in leave_apps:
        overlap_start = max(getdate(app.from_date), period_start)
        overlap_end = min(getdate(app.to_date), period_end)

        if overlap_start > overlap_end:
            continue

        days = date_diff(overlap_end, overlap_start) + 1

        if app.half_day and app.half_day_date:
            half_day_date = getdate(app.half_day_date)
            if overlap_start <= half_day_date <= overlap_end:
                days -= 0.5

        lop_days += max(days, 0)

    return round(lop_days, 2)


def _compute_arrear_amounts(process_date, employee, old_map, new_map):
    start_of_month = _month_start(process_date)
    end_of_month = get_last_day(process_date)

    days_in_month = date_diff(end_of_month, start_of_month) + 1
    old_days = date_diff(process_date, start_of_month)
    new_days = date_diff(end_of_month, process_date) + 1

    lop_days = _get_lop_days(employee, start_of_month, end_of_month)
    effective_new_days = max(flt(new_days) - flt(lop_days), 0)

    component_rows = []
    total_arrear = 0.0

    for component in COMPONENTS:
        old_amount = flt(old_map.get(component) or 0)
        new_amount = flt(new_map.get(component) or 0)
        diff = new_amount - old_amount

        if diff <= 0:
            continue

        arrear_amount = round((diff / flt(days_in_month)) * flt(effective_new_days), 2)

        if arrear_amount <= 0:
            continue

        component_rows.append(
            {
                "salary_component": component,
                "old_amount": old_amount,
                "new_amount": new_amount,
                "difference": diff,
                "arrear_amount": arrear_amount,
            }
        )
        total_arrear += arrear_amount

    return {
        "to_date": end_of_month,
        "days_in_month": days_in_month,
        "old_days": old_days,
        "new_days": new_days,
        "lop_days": lop_days,
        "effective_new_days": effective_new_days,
        "component_rows": component_rows,
        "total_arrear": round(total_arrear, 2),
    }

def validate(doc, method=None):
    if not doc.employee:
        frappe.throw("Employee is required.")

    emp = _get_employee(doc.employee)
    if not emp:
        frappe.throw("Employee not found.")

    employee_name = emp.employee_name or doc.employee
    company = doc.get("company") or emp.get("company")

    if doc.amended_from and not (doc.override_reason or "").strip():
        frappe.throw("Override Reason is required when amending Midmonth Arrear.")

    effective_date = doc.get("effective_increment_date") or emp.get("custom_effective_increment_date")
    if not effective_date:
        frappe.throw(f"Effective Increment Date is not set for {employee_name}.")

    effective_date = getdate(effective_date)

    doc.employee_name = employee_name
    if doc.meta.has_field("company") and company:
        doc.company = company

    # Keep the actual increment date
    doc.effective_increment_date = effective_date
    doc.from_date = effective_date
    doc.to_date = get_last_day(effective_date)

    existing = frappe.get_all(
        "Midmonth Arrear",
        filters={
            "employee": doc.employee,
            "from_date": effective_date,
            "docstatus": ["!=", 2],
        },
        fields=["name"],
        limit=1,
    )

    if existing and existing[0].name != doc.name:
        frappe.throw(f"Midmonth Arrear already exists for {employee_name} on {effective_date}.")

    old_ssa = _get_applicable_ssa(doc.employee, effective_date, mode="previous")
    new_ssa = _get_applicable_ssa(doc.employee, effective_date, mode="next")

    if not old_ssa:
        frappe.throw(f"No previous Salary Structure Assignment found for {employee_name} before {effective_date}.")

    if not new_ssa:
        frappe.throw(f"No Salary Structure Assignment found for {employee_name} effective on or after {effective_date}.")

    old_ctc = _get_ctc_from_ssa(old_ssa)
    new_ctc = _get_ctc_from_ssa(new_ssa)

    if flt(new_ctc) <= flt(old_ctc):
        frappe.throw(f"New CTC must be greater than old CTC for {employee_name}.")

    old_map = _calculate_breakup(old_ctc)
    new_map = _calculate_breakup(new_ctc)

    computed = _compute_arrear_amounts(
        effective_date,
        doc.employee,
        old_map,
        new_map,
    )

    if not computed["component_rows"]:
        frappe.throw(f"No positive arrear found for {employee_name}. Check the salary structure assignments.")

    doc.monthly_old_gross_salary = round(sum(old_map.values()) + FIXED_ALLOWANCES, 2)
    doc.monthly_new_gross_salary = round(sum(new_map.values()) + FIXED_ALLOWANCES, 2)

    if computed["days_in_month"]:
        if doc.meta.has_field("per_day_old"):
            doc.per_day_old = round(doc.monthly_old_gross_salary / computed["days_in_month"], 2)
        if doc.meta.has_field("per_day_new"):
            doc.per_day_new = round(doc.monthly_new_gross_salary / computed["days_in_month"], 2)

    doc.old_days = computed["old_days"]
    doc.new_days = computed["new_days"]
    doc.additional_arrear = computed["total_arrear"]

    if doc.meta.has_field("lop_days"):
        doc.lop_days = computed["lop_days"]

    if doc.meta.has_field("effective_new_days"):
        doc.effective_new_days = computed["effective_new_days"]

    if flt(doc.additional_arrear) <= 0:
        frappe.throw(f"Arrear amount is zero or negative for {employee_name}. Check the salary values and effective increment date.")

def on_submit(doc, method=None):
    emp = _get_employee(doc.employee)
    if not emp:
        frappe.throw("Employee not found.")

    company = doc.get("company") or emp.get("company")
    if not company:
        frappe.throw(f"Company is not set for employee {doc.employee}.")

    old_ssa = _get_applicable_ssa(doc.employee, doc.from_date, mode="previous")
    new_ssa = _get_applicable_ssa(doc.employee, doc.from_date, mode="next")

    old_map = _calculate_breakup(_get_ctc_from_ssa(old_ssa))
    new_map = _calculate_breakup(_get_ctc_from_ssa(new_ssa))

    computed = _compute_arrear_amounts(
        doc.from_date,
        doc.employee,
        old_map,
        new_map,
    )

    ads_meta = frappe.get_meta("Additional Salary")
    created_ads = []

    # Use the payroll date you want the arrear to appear in
    payroll_date = doc.to_date

    for row in computed["component_rows"]:
        component = row["salary_component"]

        existing_ads = frappe.db.get_value(
            "Additional Salary",
            {
                "employee": doc.employee,
                "custom_midmonth_arrear": doc.name,
                "salary_component": component,
                "docstatus": ["!=", 2],
            },
            "name",
        )
        if existing_ads:
            created_ads.append(existing_ads)
            continue

        ads_data = {
            "doctype": "Additional Salary",
            "employee": doc.employee,
            "company": company,
            "salary_component": component,
            "amount": flt(row["arrear_amount"]),
        }

        if ads_meta.has_field("employee_name"):
            ads_data["employee_name"] = doc.employee_name

        if ads_meta.has_field("payroll_date"):
            ads_data["payroll_date"] = payroll_date

        if ads_meta.has_field("type"):
            ads_data["type"] = "Earning"

        if ads_meta.has_field("overwrite_salary_structure_amount"):
            ads_data["overwrite_salary_structure_amount"] = 0

        if ads_meta.has_field("custom_midmonth_arrear"):
            ads_data["custom_midmonth_arrear"] = doc.name

        ads = frappe.get_doc(ads_data)
        ads.insert(ignore_permissions=True)
        ads.submit()
        created_ads.append(ads.name)

    if created_ads and doc.meta.has_field("additional_salary"):
        frappe.db.set_value(doc.doctype, doc.name, "additional_salary", created_ads[0])
    
def on_cancel(doc, method=None):
    ads_list = frappe.get_all(
        "Additional Salary",
        filters={
            "employee": doc.employee,
            "custom_midmonth_arrear": doc.name,
            "docstatus": 1,
        },
        fields=["name"],
    )
    for row in ads_list:
        ads = frappe.get_doc("Additional Salary", row.name)
        if ads.docstatus == 1:
            ads.cancel()