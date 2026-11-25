// Ready helpers of the page, loaded before the page's own script. Not written by the agents.
//   api(path, {method, body})   fetch JSON; shows the error in #message and throws
//   showMessage(text, kind)     "ok" or "error" in #message
//   renderTable(id, rows, columns, actions)   a table with row buttons
//   formData(form) / fillForm(form, record)   read and fill a form
//   escapeHtml(value), debounce(run, ms)
//   wireSearch(inputId, route, apply)   a search box that calls route?search=...
// Buttons with data-reset reset their form.

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join("; ")
      : body?.detail;
    showMessage(detail ?? `Error ${response.status}`, "error");
    throw new Error(`${path}: ${response.status}`);
  }
  return body;
}

function showMessage(text, kind = "ok") {
  const message = document.getElementById("message");
  message.textContent = text;
  message.className = kind;
  clearTimeout(showMessage.timer);
  showMessage.timer = setTimeout(() => { message.textContent = ""; message.className = ""; }, 4000);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// columns: [{ key: "title", label: "Title", format: (value, row) => "html" }]
// actions: [{ label: "Edit", kind: "secondary", run: (row) => ... }]
function renderTable(elementId, rows, columns, actions = []) {
  const target = document.getElementById(elementId);
  if (!rows.length) {
    target.innerHTML = '<p class="empty">Nothing here yet.</p>';
    return;
  }
  const head = columns.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("");
  const body = rows.map((row, index) => {
    const cells = columns.map((c) => `<td>${c.format ? c.format(row[c.key], row) : escapeHtml(row[c.key])}</td>`).join("");
    const buttons = actions.map((a, n) => `<button type="button" class="${a.kind ?? ""}" data-row="${index}" data-action="${n}">${escapeHtml(a.label)}</button>`).join(" ");
    return `<tr>${cells}${actions.length ? `<td class="actions">${buttons}</td>` : ""}</tr>`;
  }).join("");
  target.innerHTML = `<table><thead><tr>${head}${actions.length ? "<th></th>" : ""}</tr></thead><tbody>${body}</tbody></table>`;
  target.querySelectorAll("button[data-action]").forEach((button) => {
    button.addEventListener("click", () => actions[button.dataset.action].run(rows[button.dataset.row]));
  });
}

// The form's fields as an object: numbers as numbers, empty fields left out, no "id".
function formData(form) {
  const data = {};
  for (const element of form.elements) {
    if (!element.name || element.name === "id" || element.value === "") continue;
    data[element.name] = element.type === "number" ? Number(element.value)
      : element.type === "checkbox" ? element.checked : element.value;
  }
  return data;
}

function fillForm(form, record) {
  for (const element of form.elements) {
    if (!element.name || !(element.name in record)) continue;
    if (element.type === "checkbox") element.checked = Boolean(record[element.name]);
    else element.value = record[element.name] ?? "";
  }
  form.scrollIntoView({ behavior: "smooth" });
}

function debounce(run, ms = 300) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => run(...args), ms); };
}

// A search box that really filters one section's table: wireSearch(inputId, route, apply)
// calls route?search=... (while the user types, debounced) and gives the answer to apply.
//   wireSearch("search-books", "/api/books", (rows) => renderTable("books", rows, cols));
function wireSearch(inputId, route, apply) {
  const box = document.getElementById(inputId);
  if (!box) return;
  const run = () => api(`${route}?search=${encodeURIComponent(box.value.trim())}`).then(apply);
  box.addEventListener("input", debounce(run));
  box.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); run(); } });
}

document.addEventListener("click", (event) => {
  if (event.target.matches("[data-reset]")) event.target.form?.reset();
});
