frappe.query_reports["Daily In-Out Summary"] = {
  onload: function (report) {
    frappe.call({
      method: "hr_vfg.hr_ventureforce_global.api.attendance.get_saved_employee_filter",
      callback: function (r) {
        if (r.message) {
          const saved_employees = r.message.split(",").filter(e => e); // filter out empty strings
          if (saved_employees.length > 0) {
            report.set_filter_value("employees", saved_employees);
            frappe.query_report.refresh(); // run report only after setting employees
          }
        }
      }
    });

    frappe.query_report.get_filter('employees').df.onchange = function () {
      // no save_report logic anymore
    };
  },
  filters: [
    {
      fieldname: "date",
      label: "Date",
      fieldtype: "Date",
      default: frappe.datetime.get_today(),
      reqd: 1
    },
    {
      fieldname: "company",
      label: "Company",
      fieldtype: "Link",
      options: "Company",
      default: frappe.defaults.get_user_default("Company"),
      reqd: 1
    },
    {
      fieldname: "employees",
      label: "Employees",
      fieldtype: "MultiSelectList",
      get_data: function (txt) {
        return frappe.db.get_link_options("Employee", txt);
      },
      reqd: 1
    }
  ]
};
