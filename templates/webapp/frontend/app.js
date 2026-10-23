// Behaviour of the page: plain JavaScript in the browser, no framework, no build step.
//
// Filled by: the FRONTEND task (together with frontend/index.html).
// Relies on: the /api routes of backend/main.py, called with relative paths
//            (fetch("/api/books")), and the element ids of frontend/index.html.
//
// Rules every agent follows:
// - Use the api() helper below for every call; it shows errors in #message.
// - After a form is sent, load the lists again so the page shows the new state.
// - Start by loading the lists when the page opens.

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    document.getElementById("message").textContent = body?.detail ?? `Error ${response.status}`;
    throw new Error(`${path}: ${response.status}`);
  }
  return body;
}

// functions that load the lists, handlers of the forms, and the first load
