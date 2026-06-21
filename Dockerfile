<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Product Browser</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #F6F6F3;
    --surface: #FFFFFF;
    --text: #15171C;
    --muted: #6B7079;
    --accent: #2B4CE0;
    --accent-soft: #E8ECFD;
    --border: #E3E3DF;
    --good: #1A7F4E;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 14px;
  }

  header {
    padding: 32px 24px 20px;
    max-width: 980px;
    margin: 0 auto;
  }

  h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 26px;
    letter-spacing: -0.02em;
    margin: 0 0 4px;
  }

  .subtitle {
    color: var(--muted);
    margin: 0;
  }

  .toolbar {
    max-width: 980px;
    margin: 20px auto 0;
    padding: 0 24px;
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }

  select, button {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    padding: 9px 12px;
  }

  select { cursor: pointer; }

  button {
    cursor: pointer;
    font-weight: 600;
    transition: background 0.12s ease, border-color 0.12s ease;
  }

  button:hover:not(:disabled) {
    border-color: var(--accent);
  }

  button.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }

  button.primary:hover:not(:disabled) {
    background: #2240C4;
  }

  button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .status {
    color: var(--muted);
    font-size: 12px;
  }

  main {
    max-width: 980px;
    margin: 20px auto 60px;
    padding: 0 24px;
  }

  .table-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }

  .row {
    display: grid;
    grid-template-columns: 64px 1fr 140px 110px 200px;
    align-items: center;
    border-bottom: 1px solid var(--border);
    position: relative;
  }

  .row:last-child { border-bottom: none; }

  .row.head {
    background: #FAFAF8;
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 10px 16px;
  }

  .row.head > div { padding: 0; }

  .row:not(.head) {
    padding: 0;
  }

  .row:not(.head) > div {
    padding: 12px 16px;
  }

  .row:not(.head)::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background: var(--cat-color, var(--accent));
  }

  .id-col { color: var(--muted); }

  .price-col {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }

  .tag {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
  }

  .updated-col {
    color: var(--muted);
    font-size: 12px;
  }

  .empty, .error {
    padding: 48px 16px;
    text-align: center;
    color: var(--muted);
  }

  .error { color: #B3261E; }

  .pager {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 16px;
  }

  .cursor-chip {
    font-size: 11px;
    color: var(--muted);
    background: var(--surface);
    border: 1px dashed var(--border);
    border-radius: 6px;
    padding: 6px 10px;
    max-width: 420px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  @media (max-width: 640px) {
    .row { grid-template-columns: 48px 1fr 90px; }
    .updated-col, .id-col { display: none; }
    .row.head .updated-col, .row.head .id-col { display: none; }
  }
</style>
</head>
<body>

<header>
  <h1>Product Browser</h1>
  <p class="subtitle">~200,000 products · cursor-based pagination, newest first</p>
</header>

<div class="toolbar">
  <select id="categorySelect">
    <option value="">All categories</option>
  </select>
  <span class="status" id="status">Loading…</span>
</div>

<main>
  <div class="table-wrap">
    <div class="row head">
      <div>ID</div>
      <div>Name</div>
      <div>Category</div>
      <div style="text-align:right">Price</div>
      <div>Updated</div>
    </div>
    <div id="rows"></div>
  </div>

  <div class="pager">
    <span class="cursor-chip" id="cursorChip">cursor: (start)</span>
    <button class="primary" id="nextBtn" disabled>Next page →</button>
  </div>
</main>

<script>
  // Point this at your running FastAPI backend.
  const API_BASE_URL = "http://localhost:8000";

  const CATEGORIES = [
    "Electronics", "Fashion", "Books", "Sports", "Home",
    "Toys", "Beauty", "Automotive", "Grocery", "Health",
  ];

  // Deterministic accent color per category, derived from the palette so
  // it stays consistent without a hardcoded color per name.
  function categoryColor(category) {
    const hues = [228, 280, 12, 150, 38, 200, 330, 95, 60, 170];
    let hash = 0;
    for (let i = 0; i < category.length; i++) hash = (hash * 31 + category.charCodeAt(i)) >>> 0;
    const hue = hues[hash % hues.length];
    return `hsl(${hue} 60% 45%)`;
  }

  const els = {
    categorySelect: document.getElementById("categorySelect"),
    status: document.getElementById("status"),
    rows: document.getElementById("rows"),
    nextBtn: document.getElementById("nextBtn"),
    cursorChip: document.getElementById("cursorChip"),
  };

  let state = {
    category: "",
    cursor: null,
    hasMore: false,
    loading: false,
  };

  function init() {
    for (const cat of CATEGORIES) {
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      els.categorySelect.appendChild(opt);
    }
    els.categorySelect.addEventListener("change", () => {
      state.category = els.categorySelect.value;
      state.cursor = null;
      fetchPage({ append: false });
    });
    els.nextBtn.addEventListener("click", () => fetchPage({ append: true }));
    fetchPage({ append: false });
  }

  async function fetchPage({ append }) {
    if (state.loading) return;
    state.loading = true;
    els.nextBtn.disabled = true;
    els.status.textContent = "Loading…";

    const params = new URLSearchParams({ limit: "50" });
    if (state.category) params.set("category", state.category);
    if (append && state.cursor) params.set("cursor", state.cursor);

    try {
      const res = await fetch(`${API_BASE_URL}/products?${params.toString()}`);
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();

      if (!append) els.rows.innerHTML = "";
      if (data.items.length === 0 && !append) {
        els.rows.innerHTML = `<div class="empty">No products in this category.</div>`;
      } else {
        for (const item of data.items) els.rows.appendChild(renderRow(item));
      }

      state.cursor = data.next_cursor;
      state.hasMore = data.has_more;
      els.nextBtn.disabled = !data.has_more;
      els.cursorChip.textContent = data.next_cursor
        ? `cursor: ${data.next_cursor.slice(0, 28)}…`
        : "cursor: (end of results)";
      els.status.textContent = `Showing ${els.rows.children.length} loaded`;
    } catch (err) {
      els.rows.innerHTML = `<div class="error">Couldn't load products: ${err.message}. Is the API running at ${API_BASE_URL}?</div>`;
      els.status.textContent = "Error";
    } finally {
      state.loading = false;
    }
  }

  function renderRow(item) {
    const row = document.createElement("div");
    row.className = "row";
    row.style.setProperty("--cat-color", categoryColor(item.category));
    row.innerHTML = `
      <div class="id-col">#${item.id}</div>
      <div>${escapeHtml(item.name)}</div>
      <div><span class="tag">${escapeHtml(item.category)}</span></div>
      <div class="price-col">$${Number(item.price).toFixed(2)}</div>
      <div class="updated-col">${formatDate(item.updated_at)}</div>
    `;
    return row;
  }

  function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  init();
</script>

</body>
</html>
