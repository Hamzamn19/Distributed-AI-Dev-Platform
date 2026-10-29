// Behaviour of the page: plain JavaScript in the browser, no framework, no build step.
//
// Filled by: the FRONTEND task (together with frontend/index.html).
// Relies on: the ready helpers of frontend/lib.js (loaded first; do not write them again),
//            the /api routes of backend/main.py (relative paths such as "/api/<things>")
//            and the element ids of frontend/index.html.
//
// Rules every agent follows:
// - The helpers of lib.js:
//     await api(path, { method: "POST", body: object })   JSON in and out; errors shown
//     showMessage("Saved", "ok")
//     renderTable("list-<things>", rows,
//       [{ key: "title", label: "Title" },
//        { key: "status", label: "Status", format: (v) => `<span class="badge">${escapeHtml(v)}</span>` }],
//       [{ label: "Edit", kind: "secondary", run: (row) => fillForm(form, row) },
//        { label: "Delete", kind: "danger", run: (row) => remove(row.id) }])
//     formData(form) -> object of the named inputs (numbers as numbers, no "id")
//     fillForm(form, record), escapeHtml(value), debounce(run, 300)
// - For every record type: a load function fills its table and the search box filters it
//   (?search=...); the form adds a record (POST) or, when its hidden id is set, updates
//   it (PUT); Edit fills the form, Delete asks confirm() first; actions of the
//   requirement are row buttons too. Show states and categories with <span class="badge">.
// - Select inputs that link to another record (for example <thing>_id) are filled from
//   that record's list.
// - After every change load the lists and /api/stats again. Load everything at start.

// load functions, form handlers and row actions, then the first load
