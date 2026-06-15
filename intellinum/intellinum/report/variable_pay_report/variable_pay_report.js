// Determine if the user has admin-level access for this report
const isAdminOrHR = frappe.user.has_role("Administrator") || frappe.user.has_role("HR Manager");

frappe.query_reports["Variable Pay Report"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1,
            default: frappe.defaults.get_user_default("Company")
        },
        {
            fieldname: "payroll_month",
            label: __("Payroll Month"),
            fieldtype: "Select", // Changed from Data to Select
            options: "Jan\nFeb\nMar\nApr\nMay\nJun\nJul\nAug\nSep\nOct\nNov\nDec", // Dropdown options
            reqd: 1,
            read_only: isAdminOrHR ? 0 : 1, // Editable for Admins/HR, locked for Reporting Managers
            default: new Date().toLocaleString("en-US", { month: "short" })
        },
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Department"
        }
    ],

    get_datatable_options(options) {
        return Object.assign(options, {
            cellHeight: 42
        });
    },

	formatter(value, row, column, data, default_formatter) {
		if (!column) return value;

		if (column.fieldname === "employee" && data?.employee) {
			return `
				<a href="/app/employee/${data.employee}" class="vp-employee-link">
					${frappe.utils.escape_html(data.employee)}
				</a>
			`;
		}

		if (!data?.employee) {
			return default_formatter ? default_formatter(value, row, column, data) : value;
		}

		if (data.action === "Approved") {
			if (column.fieldname === "percentage") {
				return `
					<div class="vp-approved-percent">
						${data.percentage || 0}%
					</div>
				`;
			}

			if (column.fieldname === "performance_remark") {
				return `
					<div
						class="vp-approved-remark"
						title="${frappe.utils.escape_html(data.performance_remark || "")}">
						${frappe.utils.escape_html(data.performance_remark || "-")}
					</div>
				`;
			}

			if (column.fieldname === "action") {
				return `
					<span class="vp-approved-badge">
						✓ Approved
					</span>
				`;
			}
		} else {
			if (column.fieldname === "percentage") {
				return `
					<input
						type="number"
						min="1"
						max="100"
						class="form-control percentage-input vp-percent-input"
						placeholder="%">
				`;
			}

			if (column.fieldname === "performance_remark") {
				return `
					<input
						type="text"
						class="form-control remark-input vp-remark-input"
						placeholder="Performance remark">
				`;
			}

			if (column.fieldname === "action") {
				const emp = (data.employee || "").replace(/'/g, "\\'");
				const empName = (data.employee_name || "").replace(/'/g, "\\'");
				return `
					<button class="btn btn-primary btn-sm vp-approve-btn"
						onclick="window._vpApprove(this, '${emp}', '${empName}')">
						Approve
					</button>
				`;
			}
		}

		return default_formatter ? default_formatter(value, row, column, data) : value;
	},

	onload(report) {
		if (!$("#vp-report-style").length) {
			$("head").append(`
				<style id="vp-report-style">
					.dt-scrollable {
						border-radius: 10px;
						overflow: hidden;
					}

					.dt-cell {
						align-items: center !important;
						padding-top: 0 !important;
						padding-bottom: 0 !important;
					}

					.dt-cell__content {
						width: 100%;
					}

					.vp-employee-link {
						font-weight: 600;
						color: var(--text-color);
						text-decoration: none;
					}

					.vp-employee-link:hover {
						text-decoration: underline;
					}

					.vp-percent-input {
						height: 28px !important;
						width: 90px !important;
						text-align: center;
						font-size: 12px;
						border-radius: 6px;
					}

					.vp-remark-input {
						height: 28px !important;
						font-size: 12px;
						border-radius: 6px;
					}

					.vp-approve-btn {
						height: 28px;
						min-width: 90px;
						font-size: 12px;
						font-weight: 600;
					}

					.vp-approved-badge {
						display: inline-flex;
						align-items: center;
						gap: 4px;
						font-size: 12px;
						font-weight: 600;
						color: #1f9d55;
					}

					.vp-approved-percent {
						font-weight: 600;
						text-align: center;
					}

					.vp-approved-remark {
						color: var(--text-muted);
						overflow: hidden;
						text-overflow: ellipsis;
						white-space: nowrap;
					}

					.dt-row {
						min-height: 42px !important;
					}
				</style>
			`);
		}

		window._vpUpdateRow = function(btn, percentage, remark) {
			const $row = $(btn).closest(".dt-row");

			$row.find(".percentage-input")
				.parent()
				.html(`
					<div class="vp-approved-percent">
						${percentage}%
					</div>
				`);

			$row.find(".remark-input")
				.parent()
				.html(`
					<div class="vp-approved-remark">
						${frappe.utils.escape_html(remark || "-")}
					</div>
				`);

			$(btn)
				.parent()
				.html(`
					<span class="vp-approved-badge">
						✓ Approved
					</span>
				`);
		};

		window._vpApprove = function(btn, employee, empName) {
			const $row = $(btn).closest(".dt-row");
			const percentageVal = $row.find(".percentage-input").val();
			const remarkVal = ($row.find(".remark-input").val() || "").trim();

			if (!percentageVal) {
				frappe.msgprint(__("Please enter a percentage value for {0}.", [empName]));
				return;
			}

			const percentage = parseFloat(percentageVal);
			if (isNaN(percentage) || percentage <= 0 || percentage > 100) {
				frappe.msgprint(__("Percentage must be between 1% and 100%."));
				return;
			}

			if (!remarkVal) {
				frappe.msgprint(__("Please enter a performance remark."));
				return;
			}

			frappe.confirm(
				`Approve <b>${percentage}%</b> Variable Pay for <b>${frappe.utils.escape_html(empName)}</b>?`,
				function() {
					$(btn).prop("disabled", true).text("Approving...");

					frappe.call({
						method: "intellinum.intellinum.report.variable_pay_report.variable_pay_report.process_single_approval",
						args: {
							employee: employee,
							percentage: percentage,
							performance_remark: remarkVal,
							company: frappe.query_report.get_filter_value("company"),
							payroll_month: frappe.query_report.get_filter_value("payroll_month")
						},
						callback(r) {
							if (!r.exc) {
								window._vpUpdateRow(btn, percentage, remarkVal);
								frappe.show_alert({
									message: `${empName} approved successfully`,
									indicator: "green"
								});
								setTimeout(() => {
									frappe.query_report.refresh();
								}, 300);
							} else {
								$(btn).prop("disabled", false).text("Approve");
							}
						},
						error() {
							$(btn).prop("disabled", false).text("Approve");
						}
					});
				},
				function() {
					$(btn).prop("disabled", false).text("Approve");
				}
			);
		};
	}
};