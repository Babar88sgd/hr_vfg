import frappe
from hr_vfg.hr_ventureforce_global.report.employee_real_time_report.data_export import get_data  # ? ???? import

@frappe.whitelist()
def download_attendance_report_pdf(filters=None):
    filters = frappe.parse_json(filters)

    data = get_data(filters)

    # Summary ????? ?? ??? ???? count
    summary = {
        "total_days": len(data),
        "total_present": sum(1 for d in data if d.get("check_in_1")),
        "total_absent": sum(1 for d in data if not d.get("check_in_1")),
        "total_working_hours": ""  # Optional: working hours calculation if needed
    }

    employee = None
    if filters.get("employee"):
        try:
            employee = frappe.get_doc("Employee", filters["employee"])
        except:
            employee = None

    html = frappe.render_template("hr_vfg/templates/employee_real_time_report.html", {
        "filters": filters,
        "data": data,
        "employee": employee,
        "summary": summary
    })

    frappe.local.response.filename = "Employee-Real-Time-Report.pdf"
    frappe.local.response.filecontent = frappe.utils.pdf.get_pdf(html)
    frappe.local.response.type = "download"
