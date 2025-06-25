import frappe
from frappe.utils import get_datetime, format_time, getdate, add_days, nowdate
import calendar

def get_last_working_day(company, current_date):
    date = add_days(current_date, -1)
    holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")

    for _ in range(7):
        is_holiday = frappe.db.exists("Holiday", {
            "holiday_date": date,
            "parenttype": "Holiday List",
            "parent": holiday_list
        })
        if not is_holiday:
            return date
        date = add_days(date, -1)

    return add_days(current_date, -1)

def get_leave_status(employee, date):
    return frappe.db.exists("Leave Application", {
        "employee": employee,
        "from_date": ["<=", date],
        "to_date": [">=", date],
        "docstatus": 1,
        "status": "Approved"
    })

def execute(filters=None):
    if not filters:
        filters = {}

    date = filters.get("date") or nowdate()
    company = filters.get("company") or frappe.defaults.get_user_default("Company")

    if not date:
        frappe.throw("Please provide a date.")
    if not company:
        frappe.throw("Please select a company.")

    # Get employees
    employees = filters.get("employees") or []
    if isinstance(employees, str):
        employees = [e.strip() for e in employees.split(",") if e.strip()]
    user = frappe.session.user

    # Use saved if not provided
    if not employees:
        saved_employees = frappe.defaults.get_user_default(user, "default_attendance_employees")
        if saved_employees:
            employees = saved_employees.split(",")
        else:
            frappe.throw("Please select at least one employee (only required the first time).")

    weekday = calendar.day_name[getdate(date).weekday()]
    last_working_day = get_last_working_day(company, date)

    data = []
    emp_docs = frappe.get_all("Employee", filters={"name": ["in", employees]}, fields=["name", "employee_name", "custom_assigned_shift"])
    emp_name_map = {emp.name: emp.employee_name for emp in emp_docs}
    shift_map = {}

    for emp in emp_docs:
        shift_type = emp.custom_assigned_shift
        if shift_type:
            late_mark = frappe.db.get_value("Shift Day", {"parent": shift_type, "day": weekday}, "late_mark")
            shift_map[emp.name] = late_mark

    today_rows = frappe.db.get_all(
        "Employee Attendance Table",
        filters={"date": date},
        fields=["check_in_1", "parent"]
    )

    parent_ids = list(set(r["parent"] for r in today_rows))
    parent_map = {}
    if parent_ids:
        parents = frappe.get_all(
            "Employee Attendance",
            filters={"name": ["in", parent_ids], "employee": ["in", employees]},
            fields=["name", "employee"]
        )
        for p in parents:
            parent_map[p.name] = {"employee": p.employee}

    today_checkins = {}
    for row in today_rows:
        info = parent_map.get(row["parent"])
        if info:
            emp = info["employee"]
            today_checkins[emp] = row.get("check_in_1")

    for emp in employees:
        check_in = today_checkins.get(emp)
        late_mark = shift_map.get(emp)
        status = "Absent"

        if check_in and late_mark:
            try:
                check_in_dt = get_datetime(f"{date} {check_in}")
                late_mark_dt = get_datetime(f"{date} {late_mark}")
                status = "Late" if check_in_dt >= late_mark_dt else "On Time"
            except:
                status = "Invalid Check-in"
        elif check_in:
            status = "On Time"

        # Get last day's check-out
        last_row = frappe.db.sql("""
            SELECT t.check_out_1
            FROM `tabEmployee Attendance Table` t
            JOIN `tabEmployee Attendance` p ON t.parent = p.name
            WHERE t.date = %s AND p.employee = %s
            LIMIT 1
        """, (last_working_day, emp), as_dict=True)

        if last_row:
            if last_row[0]["check_out_1"]:
                last_check_out = format_time(last_row[0]["check_out_1"])
            elif get_leave_status(emp, last_working_day):
                last_check_out = "On Leave"
            else:
                last_check_out = ""
        elif get_leave_status(emp, last_working_day):
            last_check_out = "On Leave"
        else:
            last_check_out = ""

        data.append({
            "employee": emp,
            "employee_name": emp_name_map.get(emp),
            "check_in": format_time(check_in) if check_in else "",
            "status": status,
            "last_check_out": last_check_out
        })

    columns = [
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Data", "options": "Employee", "width": 140},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 220},
        {"label": "Check In", "fieldname": "check_in", "fieldtype": "Time", "width": 120},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": "Last Check Out", "fieldname": "last_check_out", "fieldtype": "Data", "width": 160},
    ]

    return columns, data

@frappe.whitelist()
def get_saved_employee_filter():
    user = frappe.session.user
    saved = frappe.defaults.get_user_default(user, "default_attendance_employees")
    return saved or ""
