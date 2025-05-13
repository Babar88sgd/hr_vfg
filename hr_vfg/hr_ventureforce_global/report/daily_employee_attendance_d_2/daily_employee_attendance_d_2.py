import frappe
from datetime import datetime, timedelta
from frappe.utils.pdf import get_pdf
from frappe.utils.jinja import render_template
from frappe.utils import get_url_to_report

def execute(filters=None):
    columns, data = get_columns(), get_data(filters)
    summary = get_summary(data, filters)

    # Add empty row for spacing
    data.append([""] * 11)

    # Add centered summary heading
    data.append(["", "", "", "", "", "<b> Summary </b>", "", "", "", "", ""])

    # Add summary rows in columns 2 to 5: label1, value1, label2, value2
    for i in range(0, len(summary), 2):
        label1 = f"<b>{summary[i]['label']}</b>"
        value1 = summary[i]['value']
        label2 = f"<b>{summary[i+1]['label']}</b>" if i + 1 < len(summary) else ""
        value2 = summary[i+1]['value'] if i + 1 < len(summary) else ""

        data.append(["", "", label1, value1, label2, value2, "", "", "", "", ""])

    return columns, data

def get_columns():
    return [
        "Employee ID:Data:120",
        "Employee Name:Data:180",
        "Designation:Data:120",
        "Department:Data:120",
        "Check In:Data:100",
        "Check Out:Data:100",
        "Status:Select:100",
        "A/P:Select:100",
        "Late Coming (HH:MM:SS):Data:140",
        "Early Going (HH:MM:SS):Data:140",
        "Over Time (HH:MM:SS):Data:140"
    ]

def format_time(seconds):
    return str(timedelta(seconds=int(seconds))) if seconds > 0 else "0:00:00"

def get_data(filters):
    cond = ""
    if filters.get("depart"):
        cond += f" AND emp.department = '{filters['depart']}'"
    if filters.get("employee"):
        cond += f" AND emp.employee = '{filters['employee']}'"

    records = frappe.db.sql("""
        SELECT DISTINCT emp.department, emp.employee, emply.employee_name, emply.designation,
            emptab.check_in_1, emptab.check_out_1, emp.shift_type, emptab.date
        FROM `tabEmployee Attendance` emp
        JOIN `tabEmployee Attendance Table` emptab ON emptab.parent = emp.name
        JOIN `tabEmployee` emply ON emp.employee = emply.name
        WHERE emptab.date = %s AND emply.status = 'Active' {conditions}
        ORDER BY emp.department, emp.employee
    """.format(conditions=cond), (filters.get("to"),), as_dict=True)

    seen = set()
    data = []

    filter_status = filters.get("status", "").strip().lower() if filters.get("status") else None
    filter_ap = filters.get("a_p", "").strip().lower() if filters.get("a_p") else None

    for row in records:
        unique_key = (row.employee, row.date)
        if unique_key in seen:
            continue
        seen.add(unique_key)

        check_in_time = row.check_in_1
        check_out_time = row.check_out_1
        status = ""
        ap_status = ""
        late_seconds = 0
        early_seconds = 0
        overtime_seconds = 0

        try:
            if not row.shift_type:
                raise Exception("Shift Type missing")

            day_name = datetime.strptime(str(row.date), "%Y-%m-%d").strftime('%A')
            shift_settings = frappe.get_value(
                "Shift Day",
                {"parent": row.shift_type, "day": day_name},
                ["start_time", "end_time", "minimum_hours_for_present", "minimum_hours_for_half_day", "late_mark"],
                as_dict=True,
            )

            if not shift_settings:
                raise Exception(f"Shift settings not found for {day_name}")

            shift_start = datetime.strptime(str(shift_settings.start_time), "%H:%M:%S")
            shift_end = datetime.strptime(str(shift_settings.end_time), "%H:%M:%S")
            late_mark = datetime.strptime(str(shift_settings.late_mark), "%H:%M:%S")
            min_present = shift_settings.minimum_hours_for_present or 540
            min_half = shift_settings.minimum_hours_for_half_day or 270

            if row.shift_type == "WeeklyOff":
                check_in = datetime.strptime(str(check_in_time)[-8:], "%H:%M:%S")
                check_out = datetime.strptime(str(check_out_time)[-8:], "%H:%M:%S")
                if check_out < check_in:
                    check_out += timedelta(days=1)
                worked_seconds = (check_out - check_in).total_seconds()
                if worked_seconds > 14400:
                    overtime_seconds = worked_seconds
                status = "Present"
                ap_status = "Present"

            else:
                if check_in_time and check_out_time:
                    check_in = datetime.strptime(str(check_in_time)[-8:], "%H:%M:%S")
                    check_out = datetime.strptime(str(check_out_time)[-8:], "%H:%M:%S")

                    if check_out < shift_start:
                        check_out += timedelta(days=1)

                    late_diff = (check_in - shift_start).total_seconds()
                    late_seconds = late_diff if late_diff > 0 else 0

                    if check_out < shift_end:
                        early_seconds = (shift_end - check_out).total_seconds()

                    if check_out > shift_end:
                        overtime_seconds = (check_out - shift_end).total_seconds()
                        if overtime_seconds < 14400:
                            overtime_seconds = 0

                    worked_seconds = (check_out - check_in).total_seconds()
                    if worked_seconds < min_half * 60:
                        ap_status = "Half Day"
                    elif worked_seconds < min_present * 60:
                        ap_status = "Absent"
                    else:
                        ap_status = "Present"

                    if check_in > late_mark:
                        status = "Late"
                    elif early_seconds > 0:
                        status = "Early Going"
                    else:
                        status = "On time"

                elif check_in_time and not check_out_time:
                    check_in = datetime.strptime(str(check_in_time)[-8:], "%H:%M:%S")
                    late_diff = (check_in - shift_start).total_seconds()
                    late_seconds = late_diff if late_diff > 0 else 0

                    if check_in > late_mark:
                        status = "Late"
                    else:
                        status = "On time"

                    ap_status = "Absent"
                else:
                    ap_status = "Absent"
                    status = ""

        except Exception as e:
            status = "Error"
            ap_status = "Error"
            frappe.log_error(str(e), "Attendance Report Error")

        status_clean = (status or "").strip().lower()
        ap_clean = (ap_status or "").strip().lower()

        if filter_status and filter_status != status_clean:
            continue
        if filter_ap and filter_ap != ap_clean:
            continue

        data.append([
            row.employee,
            row.employee_name,
            row.designation,
            row.department,
            check_in_time or "",
            check_out_time or "",
            status,
            ap_status,
            format_time(late_seconds),
            format_time(early_seconds),
            format_time(overtime_seconds),
        ])

    return data

def get_summary(data, filters):
    status_counts = {"On time": 0, "Late": 0, "Early Going": 0}
    ap_counts = {"Present": 0, "Absent": 0, "Half Day": 0}
    filtered_status_count = 0
    filtered_ap_count = 0

    for row in data:
        status = (row[6] or "").strip()
        ap = (row[7] or "").strip()

        if status in status_counts:
            status_counts[status] += 1
        if ap in ap_counts:
            ap_counts[ap] += 1

        if filters.get("status") and status.lower() == filters["status"].strip().lower():
            filtered_status_count += 1
        if filters.get("a_p") and ap.lower() == filters["a_p"].strip().lower():
            filtered_ap_count += 1

    summary = []

    if filters.get("status"):
        summary.append({"label": f"Total {filters['status']} (Filtered)", "value": filtered_status_count})
    else:
        for status in ["On time", "Late", "Early Going"]:
            summary.append({"label": f"Total {status}", "value": status_counts[status]})

    if filters.get("a_p"):
        summary.append({"label": f"Total {filters['a_p']} (Filtered)", "value": filtered_ap_count})
    else:
        for ap in ["Present", "Absent", "Half Day"]:
            summary.append({"label": f"Total {ap}", "value": ap_counts[ap]})

    return summary

@frappe.whitelist()
def download_attendance_pdf(filters=None):
    import json
    if isinstance(filters, str):
        filters = json.loads(filters)

    columns, data = execute(filters)
    summary = get_summary(data, filters)

    context = {
        "filters": filters,
        "data": [
            {
                "name": row[1],
                "date": filters.get("to"),
                "day": frappe.utils.formatdate(filters.get("to"), "dddd"),
                "actual_in_time": row[4],
                "actual_out_time": row[5],
                "late_arrival": row[8],
                "day_status": row[6],
                "att_status": row[7],
                "work_hours": "",  # Add if calculated
                "total_hours": "",  # Add if calculated
                "overtime": row[10],
                "early_going": row[9],
            }
            for row in data if row[1]
        ],
        "summary": summary,
    }

    html = render_template("custom_reports/templates/employee_attendance_pdf.html", context)
    pdf = get_pdf(html)

    frappe.local.response.filename = "employee_attendance_report.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"
