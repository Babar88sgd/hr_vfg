import frappe

@frappe.whitelist()
def get_saved_employee_filter():
    user = frappe.session.user
    saved = frappe.defaults.get_user_default(user, "default_attendance_employees")
    return saved or ""
