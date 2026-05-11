// Copyright (c) 2026, ibsl and contributors
// For license information, please see license.txt

// frappe.query_reports["New Leave Allocation Report"] = {
// 	"filters": [
//
// 	]
// };








frappe.query_reports["New Leave Allocation Report"] = {

    filters: [
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
        { fieldname: "to_date",   label: __("To Date"),   fieldtype: "Date" },
    ],

    formatter: function (value, row, column, data, default_formatter) {

        if (column.fieldname === "action") {
            if (data && data.status === "Pending") {
                const emp     = (data.employee || "").replace(/'/g, "\\'");
                const empName = (data.employee_name || "").replace(/'/g, "\\'");
                const conf    = (data.final_confirmation_date || "");
                const leaves  = parseInt(data.leave_to_be_allocated) || 0;

                return `<button
                    class="btn btn-default btn-xs jb-alloc-btn"
                    onclick="window._jbAllocate(this,'${emp}','${empName}','${conf}',${leaves})">
                    Allocate
                </button>`;
            }
            return data && data.status === "Allocated" ? `&#10003; Done` : "";
        }

        return default_formatter(value, row, column, data);
    },

    onload: function (report) {

        window._jbAllocate = function (btn, employee, empName, confDate, leaves) {
            const yearEnd = frappe.datetime.year_end();

            frappe.confirm(
                `Do you want to allocate ${leaves} Paid Leave(s) to ${empName}?<br>
                 <small>From: ${confDate} &nbsp;&rarr;&nbsp; To: ${yearEnd}</small>`,

                function () {
                    const _origMsgprint = frappe.msgprint;
                    frappe.msgprint = () => {};

                    // Disable button immediately to prevent double click
                    $(btn).prop("disabled", true).text("Allocating...");

                    frappe.call({
                        method: "frappe.client.insert",
                        args: {
                            doc: {
                                doctype             : "Leave Allocation",
                                employee            : employee,
                                leave_type          : "Paid Leave",
                                from_date           : confDate,
                                to_date             : yearEnd,
                                new_leaves_allocated: leaves,
                            },
                        },
                        freeze        : true,
                        freeze_message: "Creating Leave Allocation...",
                        error_handlers: {
                            OverlapError: function() {
                                frappe.msgprint = _origMsgprint;
                                // Already allocated — update row instantly
                                window._jbUpdateRow(btn);
                                frappe.show_alert({ message: `Already allocated for ${empName}.`, indicator: "orange" });
                            },
                            OverAllocationError: function() {
                                frappe.msgprint = _origMsgprint;
                                $(btn).prop("disabled", false).text("Allocate");
                                frappe.show_alert({ message: `Exceeds max limit for ${empName}.`, indicator: "red" });
                            }
                        },
                        callback: function (r) {
                            if (r.exc || !r.message) {
                                frappe.msgprint = _origMsgprint;
                                $(btn).prop("disabled", false).text("Allocate");
                                return;
                            }
                            frappe.call({
                                method: "frappe.client.submit",
                                args  : { doc: r.message },
                                freeze: true,
                                freeze_message: "Submitting...",
                                callback: function (res) {
                                    frappe.msgprint = _origMsgprint;
                                    if (res.exc) {
                                        $(btn).prop("disabled", false).text("Allocate");
                                        frappe.show_alert({ message: "Submit failed.", indicator: "red" });
                                        return;
                                    }
                                    // ✅ Instantly update row — no page refresh
                                    window._jbUpdateRow(btn);
                                    frappe.show_alert({
                                        message  : `Leave allocated for ${empName}!`,
                                        indicator: "green",
                                    });
                                },
                            });
                        },
                    });
                },
                // On "No" — re-enable button
                function() {
                    $(btn).prop("disabled", false).text("Allocate");
                }
            );
        };

        // Updates Status cell → "Allocated", Action cell → "✓ Done" instantly
        window._jbUpdateRow = function(btn) {
            const $cell   = $(btn).closest(".dt-cell");
            const $row    = $cell.closest(".dt-row");

            // Update Action cell
            $cell.find(".dt-cell__content").html("&#10003; Done");

            // Find Status cell in same row and update it
            $row.find(".dt-cell").each(function() {
                const colId = $(this).attr("data-col-index");
                const text  = $(this).find(".dt-cell__content").text().trim();
                if (text === "Pending") {
                    $(this).find(".dt-cell__content").text("Allocated");
                }
            });
        };
    },
};
