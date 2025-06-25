// Copyright (c) 2025, VFG and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Real Time Report"] = {
    "filters": [
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            default: frappe.datetime.month_start()
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            default: frappe.datetime.month_end()
        },
        {
            fieldname: "employee",
            label: "Employee",
            fieldtype: "Link",
            options: "Employee"
        },
        {
            fieldname: "department",
            label: "Department",
            fieldtype: "Link",
            options: "Department"
        }
    ],

    onload: function(report) {
        report.page.add_inner_button(__('Download PDF'), function() {
            let filters = report.get_filter_values();

            frappe.call({
                method: "hr_vfg.hr_ventureforce_global.report.employee_real_time_report.pdf_export.download_attendance_report_pdf",
                args: {
                    filters: JSON.stringify(filters) // Important: stringify before sending
                },
                callback: function(r) {
                    if (r.message) {
                        // Open the PDF file URL in a new tab
                        window.open(r.message, '_blank');
                    } else {
                        frappe.msgprint("No PDF was generated.");
                    }
                },
                error: function(err) {
                    frappe.msgprint("An error occurred while generating the PDF.");
                    console.error(err);
                }
            });
        });
    }
};
