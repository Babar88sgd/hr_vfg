frappe.pages['attendance-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'HR Attendance Dashbord',
		single_column: true
	});
}