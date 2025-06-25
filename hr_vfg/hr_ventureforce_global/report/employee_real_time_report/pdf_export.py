import frappe
from frappe import _
from frappe.utils.pdf import get_pdf
from frappe.utils.jinja import render_template
import json

# ???? import (?? ?? get_data ?? ????? ???? ???? ?????)
from hr_vfg.hr_ventureforce_global.report.employee_real_time_report.data_export import get_data

@frappe.whitelist()
def download_attendance_report_pdf(filters):
    if isinstance(filters, str):
        filters = json.loads(filters)

    data = get_data(filters)

    employee = None
    if filters.get("employee"):
        employee = frappe.get_doc("Employee", filters.get("employee"))

    context = {
        "filters": filters,
        "data": data,
        "employee": employee
    }

    html = render_template("hr_vfg/hr_ventureforce_global/templates/employee_real_time_report.html", context)

    pdf_file = get_pdf(html)
    frappe.local.response.filename = "Attendance Report.pdf"
    frappe.local.response.filecontent = pdf_file
    frappe.local.response.type = "download"
