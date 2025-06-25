import frappe
from frappe.utils import format_time, formatdate, getdate
from datetime import datetime, timedelta

def execute(filters=None):
    if not filters:
        return [], []

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    employee_filter = filters.get("employee")
    department = filters.get("department")

    # SQL conditions for Employee Attendance Table
    conditions = ["att.date >= '2024-01-01'"]
    values = {}
    if from_date and to_date:
        conditions.append("att.date BETWEEN %(from_date)s AND %(to_date)s")
        values.update({"from_date": from_date, "to_date": to_date})
    if employee_filter:
        conditions.append("ea.employee = %(employee)s")
        values["employee"] = employee_filter
    if department:
        conditions.append("ea.department = %(department)s")
        values["department"] = department
    condition_sql = " AND ".join(conditions)

    # Fetch attendance records
    records = frappe.db.sql(f"""
        SELECT
            ea.employee,
            ea.employee_name,
            ea.shift_type,
            att.date AS attendance_date,
            att.check_in_1,
            att.check_out_1
        FROM `tabEmployee Attendance Table` att
        JOIN `tabEmployee Attendance` ea ON att.parent = ea.name
        WHERE {condition_sql}
        ORDER BY att.date, ea.employee
    """, values, as_dict=True)

    data = []
    summary = {
        "On Time": 0,
        "Early Departure": 0,
        "Late Arrival": 0,
        "Leave": 0,
        "Total Present": 0,
        "Holiday": 0,
        "Gazetted Holiday": 0,
        "Weekly Off": 0,
        "Absent": 0
    }

    for row in records:
        attendance_date = row.attendance_date
        time_in = row.check_in_1
        time_out = row.check_out_1

        working_hours = ""
        late_hr = ""
        early_hr = ""
        remarks = ""
        status = ""

        if not time_in:
            status = "Absent"
            summary["Absent"] += 1
        else:
            status = "Present"
            summary["Total Present"] += 1

        data.append({
            "employee": row.employee,
            "employee_name": row.employee_name,
            "attendance_date": formatdate(attendance_date),
            "check_in_1": format_time(time_in) if time_in else "",
            "check_out_1": format_time(time_out) if time_out else "",
            "working_hours": working_hours,
            "status": status
        })

    return [], data


# ------------------ PDF Export ------------------

@frappe.whitelist()
def download_attendance_report_pdf(filters=None):
    filters = frappe.parse_json(filters)
    _, data = execute(filters)

    summary = {
        "total_days": len(data),
        "total_present": sum(1 for d in data if d.get("status") == "Present"),
        "total_absent": sum(1 for d in data if d.get("status") == "Absent"),
        "total_working_hours": ""  # Optional: add calculation
    }

    employee = None
    if filters.get("employee"):
        try:
            employee = frappe.get_doc("Employee", filters["employee"])
        except:
            pass

    html = frappe.render_template("hr_vfg/templates/employee_real_time_report.html", {
        "filters": filters,
        "data": data,
        "employee": employee,
        "summary": summary
    })

    frappe.local.response.filename = "Employee-Real-Time-Report.pdf"
    frappe.local.response.filecontent = frappe.utils.pdf.get_pdf(html)
    frappe.local.response.type = "download"
