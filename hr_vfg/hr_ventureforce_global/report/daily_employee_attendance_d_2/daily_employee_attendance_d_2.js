frappe.query_reports["Daily Employee Attendance D-2"] = {
    "filters": [
        {
            "fieldname": "to",
            "label": "Date",
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "employee",
            "label": "Employee",
            "fieldtype": "Link",
            "options": "Employee"
        },
        {
            "fieldname": "depart",
            "label": "Department",
            "fieldtype": "Link",
            "options": "Department"
        },
        {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Select",
            "options": ["", "On time", "Late", "Early Going"]
        },
        {
            "fieldname": "a_p",
            "label": "A/P",
            "fieldtype": "Select",
            "options": ["", "Present", "Absent", "Half Day"]
        }
    ]
}
