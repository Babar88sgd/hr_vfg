import frappe
from datetime import datetime, timedelta

def execute(filters=None):
    columns, data = get_columns(), get_data(filters)
    summary = get_summary(data, filters)

    data.append([""] * 12)
    data.append(["", "", "", "", "", "<b> Summary </b>", "", "", "", "", "", ""])

    for i in range(0, len(summary), 2):
        label1 = f"<b>{summary[i]['label']}</b>"
        value1 = summary[i]['value']
        label2 = f"<b>{summary[i+1]['label']}</b>" if i + 1 < len(summary) else ""
        value2 = summary[i+1]['value'] if i + 1 < len(summary) else ""
        data.append(["", "", label1, value1, label2, value2, "", "", "", "", "", ""])

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
        "Total Working Hours:Data:140",
        "Over Time (HH:MM:SS):Data:140",
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
        total_working_seconds = 0

        try:
            if not row.shift_type:
                raise Exception("Shift Type missing")

            day_name = datetime.strptime(str(row.date), "%Y-%m-%d").strftime('%A')
            shift_settings = frappe.get_value(
                "Shift Day",
                {"parent": row.shift_type, "day": day_name},
                ["start_time", "end_time", "minimum_hours_for_present", "minimum_hours_for_half_day",
                 "late_mark", "day_type", "half_day", "max_early"],
                as_dict=True,
            )

            if not shift_settings:
                raise Exception(f"Shift settings not found for {day_name}")

            shift_start = datetime.strptime(str(shift_settings.start_time), "%H:%M:%S")
            shift_end = datetime.strptime(str(shift_settings.end_time), "%H:%M:%S")
            late_mark = datetime.strptime(str(shift_settings.late_mark), "%H:%M:%S")
            min_present = (shift_settings.minimum_hours_for_present or 540) * 60
            min_half = (shift_settings.minimum_hours_for_half_day or 270) * 60
            day_type = shift_settings.day_type

            check_in = datetime.strptime(str(check_in_time)[-8:], "%H:%M:%S") if check_in_time else None
            check_out = datetime.strptime(str(check_out_time)[-8:], "%H:%M:%S") if check_out_time else None

            is_night_shift = shift_start > shift_end or row.shift_type == "Night"
            if is_night_shift:
                shift_end += timedelta(days=1)
                if check_out and check_in and check_out < check_in:
                    check_out += timedelta(days=1)

            if day_type == "WeeklyOff":
                if check_in and check_out:
                    total_working_seconds = (check_out - check_in).total_seconds()
                    overtime_seconds = total_working_seconds if total_working_seconds > 4 * 3600 else 0
                ap_status = status = "Present"
            else:
                if check_in and check_out:
                    total_working_seconds = (check_out - check_in).total_seconds()
                    late_diff = (check_in - shift_start).total_seconds()
                    late_seconds = late_diff if late_diff > 0 else 0

                    half_day_flag = False
                    if shift_settings.half_day:
                        half_day_start_dt = datetime.combine(check_out.date(), datetime.strptime(str(shift_settings.half_day), "%H:%M:%S").time())
                        max_early_dt = half_day_start_dt + timedelta(minutes=shift_settings.max_early or 0)
                        if half_day_start_dt <= check_out < max_early_dt:
                            status = "Half Day"
                            half_day_flag = True
                        elif max_early_dt <= check_out <= shift_end:
                            early_seconds = (shift_end - check_out).total_seconds()
                            status = "Early Going"
                        else:
                            status = "On time"
                    else:
                        status = "On time"

                    if total_working_seconds < min_half:
                        status = "Absent"
                        half_day_flag = False

                    if not half_day_flag:
                        if check_in > late_mark:
                            status = "Late"
                        elif status not in ["Early Going", "Half Day"]:
                            status = "On time"

                    if total_working_seconds < min_half:
                        ap_status = "Absent"
                    elif total_working_seconds < min_present:
                        ap_status = "Half Day"
                    else:
                        ap_status = "Present"

                    if check_out > shift_end:
                        overtime_seconds = (check_out - shift_end).total_seconds()
                    else:
                        overtime_seconds = 0

                elif check_in and not check_out:
                    late_diff = (check_in - shift_start).total_seconds()
                    late_seconds = late_diff if late_diff > 0 else 0
                    status = "Late" if check_in > late_mark else "On time"
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
            str(check_in_time) if check_in_time else "",
            str(check_out_time) if check_out_time else "",
            status,
            ap_status,
            format_time(late_seconds),
            format_time(early_seconds),
            format_time(total_working_seconds),
            format_time(overtime_seconds),
        ])

    return data

def get_summary(data, filters):
    status_labels = ["On Time", "Late", "Half Day", "Early Going"]
    ap_labels = ["Present", "Absent"]

    # Normalize filters
    filter_status = (filters.get("status") or "").strip().title()
    filter_ap = (filters.get("a_p") or "").strip().title()

    # Initialize counts
    count_map = {label: 0 for label in status_labels + ap_labels}

    for row in data:
        # Normalize values from row
        status_val = (row[6] or "").strip().title()
        ap_val = (row[7] or "").strip().title()

        # Apply filters
        if filter_status and status_val != filter_status:
            continue
        if filter_ap and ap_val != filter_ap:
            continue

        if status_val in status_labels:
            count_map[status_val] += 1
        if ap_val in ap_labels:
            count_map[ap_val] += 1

    # Prepare summary based on filters
    summary = []

    if filter_status and not filter_ap:
        # Only Status filter is applied ? show all A/P values + filtered Status
        for label in ap_labels:
            summary.append({
                "label": label,
                "value": count_map[label],
                "col": 3
            })
        summary.append({
            "label": filter_status,
            "value": count_map[filter_status],
            "col": 3
        })

    elif filter_ap and not filter_status:
        # Only A/P filter is applied ? show all Status values + filtered A/P
        for label in status_labels:
            summary.append({
                "label": label,
                "value": count_map[label],
                "col": 3
            })
        summary.append({
            "label": filter_ap,
            "value": count_map[filter_ap],
            "col": 3
        })

    else:
        # No filters or both filters ? show all 6 values
        for label in status_labels + ap_labels:
            summary.append({
                "label": label,
                "value": count_map[label],
                "col": 3
            })

    return summary
def execute(filters=None):
    columns, data = get_columns(), get_data(filters)
    summary = get_summary(data, filters)

    # ? Step 1: Add blank row
    data.append([""] * 12)

    # ? Step 2: Add summary heading in column 3
    data.append(["", "", "<b> Summary </b>", "", "", "", "", "", "", "", "", ""])

    # ? Step 3: Add summary lines (starting from column 3)
    for i in range(0, len(summary), 2):
        label1 = f"<b>{summary[i]['label']}</b>"
        value1 = summary[i]['value']
        label2 = f"<b>{summary[i+1]['label']}</b>" if i + 1 < len(summary) else ""
        value2 = summary[i+1]['value'] if i + 1 < len(summary) else ""
        data.append(["", "", label1, value1, label2, value2, "", "", "", "", "", ""])

    return columns, data

