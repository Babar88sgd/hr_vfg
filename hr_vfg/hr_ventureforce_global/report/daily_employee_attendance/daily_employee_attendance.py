import frappe
from datetime import datetime, timedelta, date

def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)

    # Ensure each row matches the number of columns
    for i, row in enumerate(data):
        if len(row) < len(columns):
            data[i] += [""] * (len(columns) - len(row))
        elif len(row) > len(columns):
            data[i] = row[:len(columns)]

    return columns, data

def get_columns(filters):
    return [
        "Employee ID:Data:120",
        "Employee Name:Data:180",
        "Designation:Data:120",
        "Department:Data:120",
        "Check In:Data:100",
        "Check Out:Data:100",
        "Status:Data:100",
        "A/P:Data:100",
        "Late Coming (HH:MM:SS):Data:140",
        "Early Going (HH:MM:SS):Data:140",
        "Over Time (HH:MM:SS):Data:140"
    ]

def get_data(filters):
    cond = ""
    if filters.get("depart"):
        cond += f" and emp.department = '{filters.get('depart')}'"
    if filters.get("employee"):
        cond += f" and emp.employee = '{filters.get('employee')}'"

    records = frappe.db.sql("""
        SELECT
            emp.department,
            emp.employee,
            emply.employee_name,
            emply.designation,
            emptab.check_in_1,
            emptab.check_out_1,
            emptab.early_going_hours,
            emptab.late_sitting,
            emptab.shift_in
        FROM `tabEmployee Attendance` AS emp
        JOIN `tabEmployee Attendance Table` AS emptab ON emptab.parent = emp.name
        JOIN `tabEmployee` AS emply ON emp.employee = emply.name
        WHERE emptab.date = %s {conditions} AND emply.status = 'Active'
        ORDER BY emptab.date, emp.department
    """.format(conditions=cond), (filters.get('to'),), as_dict=True)

    data = []
    total_lates = 0
    total_presents = 0
    total_absents = 0
    total_half_days = 0
    total_early_goings = 0

    for item in records:
        late_minutes = 0
        early_minutes = 0
        overtime_minutes = 0
        ap_status = ""
        status_list = []

        try:
            shift_in = datetime.strptime(str(item.shift_in), "%H:%M:%S") if item.shift_in else None
            check_in_time = datetime.strptime(str(item.check_in_1)[-8:], "%H:%M:%S") if item.check_in_1 else None
            check_out_time = datetime.strptime(str(item.check_out_1)[-8:], "%H:%M:%S") if item.check_out_1 else None

            today = date.today()
            check_in = datetime.combine(today, check_in_time.time()) if check_in_time else None
            check_out = datetime.combine(today, check_out_time.time()) if check_out_time else None
            if check_in and check_out and check_out < check_in:
                check_out += timedelta(days=1)
            if shift_in:
                shift_in = datetime.combine(today, shift_in.time())
                shift_out = shift_in + timedelta(hours=9)

            # Late Coming
            if check_in and shift_in:
                diff = int((check_in - shift_in).total_seconds() / 60)
                late_minutes = diff if diff > 0 else 0
                if late_minutes >= 16:
                    status_list.append("Late")
                else:
                    status_list.append("On time")

            # Early Going (only if check_out before shift_out)
            if check_out and shift_in:
                if check_out < shift_out:
                    early_minutes = int((shift_out - check_out).total_seconds() / 60)
                    status_list.append("Early Going")
                    total_early_goings += 1

                # Overtime
                overtime_diff = int((check_out - shift_out).total_seconds() / 60)
                if overtime_diff > 60:
                    overtime_minutes = overtime_diff

            # A/P Logic (Early Going NOT included here anymore)
            if not check_in or not check_out:
                ap_status = "Absent"
                total_absents += 1
                status = ""
            else:
                total_worked_minutes = int((check_out - check_in).total_seconds() / 60)
                if total_worked_minutes < 270:
                    ap_status = "Absent"
                    total_absents += 1
                elif total_worked_minutes < 480:
                    ap_status = "Half Day"
                    total_half_days += 1
                else:
                    ap_status = "Present"
                    total_presents += 1

                status = ", ".join(status_list) if status_list else ""

        except Exception as e:
            frappe.log_error(message=str(e), title="Attendance Parse Error")
            status = "Error"
            ap_status = "Error"

        row = [
            item.employee,
            item.employee_name,
            item.designation,
            item.department,
            item.check_in_1 or "",
            item.check_out_1 or "",
            status,
            ap_status,
            str(timedelta(minutes=late_minutes)),
            str(timedelta(minutes=early_minutes)),
            str(timedelta(minutes=overtime_minutes)),
        ]
        data.append(row)

    # Add summary rows at the bottom
    data.append([""] * 6 + ["", "<b>Total Presents</b>", total_presents, "", ""])	
    data.append([""] * 6 + ["", "<b>Total Early Going</b>", total_early_goings, "", ""])
    data.append([""] * 6 + ["", "<b>Total Absents</b>", total_absents, "", ""])
    data.append([""] * 6 + ["", "<b>Total Half Days</b>", total_half_days, "", ""])

    return data
