# Product Browser

A backend for browsing ~200,000 products with **fast, consistent pagination** —
no OFFSET, no duplicates, no missed rows, even while data changes underneath
the user mid-browse.

```
GET  /products?category=Electronics&cursor=...&limit=50
POST /products
PUT  /products/{id}
```

---

## 1. Quick start (local)

```bash
git clone <repo> && cd product-browser
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # fill in DATABASE_URL
alembic upgrade head          # create the products table + indexes
python scripts/seed_products.py   # seed ~200,000 products (a few minutes)

uvicorn app.main:app --reload
# → http://localhost:8000/docs (interactive Swagger UI)
```

Open `frontend/index.html` directly in a browser (it calls
`http://localhost:8000` by default) for the bonus UI.

Run tests (no Postgres needed — they use an in-memory SQLite DB):

```bash
pytest -v
```

---

## 2. Project structure

```
product-browser/
├── app/
│   ├── main.py          FastAPI app, CORS, health check
│   ├── config.py         Settings loaded from environment / .env
│   ├── database.py       Engine, session factory, get_db dependency
│   ├── models.py         SQLAlchemy Product model
│   ├── schemas.py        Pydantic request/response schemas
│   ├── pagination.py      Cursor encode/decode (base64 JSON)
│   └── routes.py         GET/POST/PUT /products endpoints
├── scripts/
│   └── seed_products.py    Bulk-generates 200,000 products
├── alembic/                 Migrations (creates table + 2 indexes)
├── tests/
│   ├── test_pagination.py    Ordering, no-dup/no-miss, concurrency
│   └── test_products.py    Create / read / update
├── frontend/index.html       Minimal bonus UI
├── requirements.txt, Dockerfile, .env.example
```

---

## 3. Architecture decisions

**FastAPI** — async-native, Pydantic-validated request/response models give
free input validation and OpenAPI docs, and its dependency-injection system
(`Depends(get_db)`) keeps DB sessions cleanly scoped per request.

**PostgreSQL** — the only requirement that actually matters for this
assignment is **row-value (tuple) comparison support**:
`WHERE (updated_at, id) < (x, y)` evaluated as a single composite predicate
that a composite index can satisfy directly. Postgres supports this natively
and efficiently; it's also the natural choice for a relational, indexed,
200k-row catalog with growth into full-text search or read replicas later.

**Cursor (keyset) pagination instead of OFFSET/LIMIT** — see §5 for the full
performance argument. Short version: OFFSET forces Postgres to scan and
discard every skipped row on every page; keyset pagination jumps straight to
the right spot using the index, so every page costs the same regardless of
how deep you are.

**Composite indexes** — `(updated_at DESC, id DESC)` and
`(category, updated_at DESC, id DESC)` exist because the pagination query's
`ORDER BY` and `WHERE` clauses both need to be satisfied by a single index
scan, not a sort step. See §6.

---

## 4. The cursor

A cursor is the **opaque, base64-encoded** sort key of the last row a client
saw:

```json
{ "updated_at": "2026-06-18T09:14:02.331", "id": 184213 }
```

`GET /products` returns:

```json
{
  "items": [ ... up to `limit` products ... ],
  "next_cursor": "eyJ1cGRhdGVkX2F0IjoiMjAyNi0wNi0xOFQwOTo...",
  "has_more": true
}
```

To get the next page, the client passes that `next_cursor` straight back —
it never constructs or interprets it. Internally (`app/crud.py`):

```python
query = query.filter(
    tuple_(Product.updated_at, Product.id) < (cursor_updated_at, cursor_id)
)
query = query.order_by(desc(Product.updated_at), desc(Product.id))
rows = query.limit(limit + 1).all()   # +1 to compute has_more cheaply
```

This is exactly the inequality the assignment specifies, translated into
SQLAlchemy's row-value comparison construct (`tuple_(...)`), which compiles
to literal SQL `WHERE (updated_at, id) < (:1, :2)`.

**Why `(updated_at, id)` and not `updated_at` alone?** Timestamps aren't
unique — two products can be updated in the same millisecond. Without `id`
as a tiebreaker, rows sharing a timestamp could be skipped or repeated
depending on how the database happens to order ties. Appending `id` (which
*is* unique) makes the sort key strictly unique, which is what keyset
pagination requires to be exact.

---

## 5. Performance: why not OFFSET?

**OFFSET is O(offset + limit), not O(limit).** `OFFSET 100000 LIMIT 50` does
not jump to row 100,000 — Postgres still has to walk through (and discard)
the first 100,000 matching rows on every single request, even though they
were already fetched in earlier pages. As the catalog grows, page 2,000 gets
proportionally slower than page 1. With 200,000 rows, the last pages
of an OFFSET-paginated browse can be 100x+ slower than the first.

**Keyset pagination is O(limit).** `WHERE (updated_at, id) < (x, y) ORDER BY
updated_at DESC, id DESC LIMIT 50` is a direct index seek: Postgres uses the
composite index to land exactly at the boundary defined by the cursor and
reads forward exactly `limit` rows. Page 1 and page 4,000 cost the same.

**Composite indexes are necessary, not optional**, because the query has to
satisfy both a filter (`category =`, optionally) and a sort
(`updated_at DESC, id DESC`) from a *single* index — otherwise Postgres
either falls back to a sequential scan or has to sort matching rows in
memory after fetching them, both of which scale badly at 200k+ rows.
`idx_products_updated_id` covers the unfiltered case; the leading
`category` column in `idx_products_category_updated_id` lets Postgres seek
directly to a category's slice of rows, already in the right order.

---

## 6. Consistency guarantees (no duplicates, no missing rows)

This is the part of the assignment that's easy to get subtly wrong with
OFFSET pagination, so it's worth spelling out precisely.

**The failure mode with OFFSET:** if a new row is inserted (and it sorts
ahead of the current page, e.g. it's newest), every row after it shifts down
by one position. A client mid-pagination using `OFFSET 50`, `OFFSET 100`, …
will see the row that *used to be* at offset 50 again at offset 51 — a
duplicate — or skip a row entirely if one was deleted ahead of the cursor.
OFFSET pagination's correctness silently depends on the table not changing
between requests, which the assignment explicitly says cannot be assumed.

**Why keyset pagination doesn't have this problem:** the cursor isn't a
*position* (an offset that shifts when rows are added/removed) — it's a
*value* (the last row's actual sort key). The next page query
(`WHERE (updated_at, id) < cursor`) is defined relative to data the client
has already seen, not relative to the table's current size or shape.

Concretely:

- **New product inserted while browsing** → it gets `updated_at = now()`,
  which is *newer* than anything the user has paginated past. It sorts
  *ahead of* the cursor, so it lands on a page the user already turned —
  the user simply never sees it in this browse session (consistent with
  "newest first": new items appear if you restart from page 1, not by
  retroactively rewriting pages you've already read). It is never
  duplicated and never causes another row to be skipped.
- **Existing, not-yet-seen product is updated** → its `updated_at` also
  jumps to `now()`, making it sort *newer* than the cursor. Same as above:
  it moves ahead of where the user currently is and is unaffected by — and
  doesn't affect — the rest of the page boundary.
- **Existing, already-seen product is updated** → it now sorts as the
  newest row, but the cursor has already moved past where it used to be;
  it doesn't reappear, because the comparison is purely `< cursor`, with no
  re-evaluation of rows already walked past.
- **No row is ever skipped**, because the `<` boundary is a *value*
  comparison, not a count: every row with a sort key strictly less than the
  cursor is still reachable on a future page, regardless of how many rows
  were inserted or updated above it.

This is the standard "no phantom reads across pages" property of keyset
pagination, and it's covered by `tests/test_pagination.py`
(`test_pagination_stable_when_new_item_inserted_during_browsing`,
`test_pagination_stable_when_earlier_item_updated_during_browsing`,
`test_pagination_no_duplicates_no_missing`).

**Trade-off worth naming honestly:** this guarantees consistency *relative
to data the user has already seen* — it does not retroactively show a newly
inserted product on a page the user already turned past (that would require
either re-running the whole query or a delta/changefeed mechanism). For a
"browse a catalog" UX, that's the correct and expected behavior; for a
live-updating feed, you'd add a way to refresh from the top.

---

## 7. API reference

### `GET /products`

| Param      | Type   | Default | Notes                                  |
|------------|--------|---------|-----------------------------------------|
| `category` | string | none    | Exact match (e.g. `Electronics`)        |
| `cursor`   | string | none    | From a previous response's `next_cursor`|
| `limit`    | int    | 50      | 1–200                                    |

```json
{
  "items": [
    {
      "id": 184213,
      "name": "Premium Headphones #184213",
      "category": "Electronics",
      "price": "459.99",
      "created_at": "2026-04-02T11:03:10",
      "updated_at": "2026-06-18T09:14:02.331"
    }
  ],
  "next_cursor": "eyJ1cGRhdGVkX2F0IjoiMjAyNi0wNi0xOFQwOTo...",
  "has_more": true
}
```

### `POST /products`

```json
{ "name": "Wireless Mouse", "category": "Electronics", "price": "29.99" }
```
→ `201` with the created product (`updated_at` set by the database).

### `PUT /products/{id}`

Partial update — send only the fields you want to change:

```json
{ "price": "24.99" }
```
→ `200` with the updated product. `updated_at` always changes (enforced
both by the column's `onupdate` and explicitly in `crud.update_product`).

---

## 8. Deployment

### Neon PostgreSQL setup

1. Create a free project at [neon.tech](https://neon.tech).
2. Copy the connection string from the project dashboard (it looks like
   `postgresql://user:pass@ep-xxxx.region.aws.neon.tech/dbname?sslmode=require`).
3. Rewrite the scheme for SQLAlchemy + psycopg2:
   `postgresql+psycopg2://user:pass@ep-xxxx.../dbname?sslmode=require`.
4. Set that as `DATABASE_URL`.

### Render deployment

1. Push this repo to GitHub.
2. In Render: **New → Web Service**, connect the repo.
3. Build command: `pip install -r requirements.txt`
   Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   (or use the included `Dockerfile` and pick "Docker" as the environment).
4. Add environment variable `DATABASE_URL` (the Neon string from above).
5. After the first deploy, open a Render shell (or run locally pointed at
   the same `DATABASE_URL`) and run:
   ```bash
   alembic upgrade head
   python scripts/seed_products.py
   ```
6. Visit `https://<your-service>.onrender.com/docs`.

### Environment variables

| Variable        | Required | Example                                              |
|-----------------|----------|-------------------------------------------------------|
| `DATABASE_URL`  | yes      | `postgresql+psycopg2://user:pass@host:5432/db`        |
| `CORS_ORIGINS`  | no       | `["https://your-frontend.com"]` (defaults to `["*"]`) |

---

## 9. Future improvements

- **Redis caching** for hot, unfiltered first pages (highest-traffic, most
  cacheable query).
- **Full-text search / ElasticSearch** for name search — keyset pagination
  as built here assumes a single, fully-ordered sort key, which doesn't mix
  cleanly with relevance-ranked search results.
- **Read replicas** to scale read throughput independently of writes, once
  traffic outgrows a single Postgres instance.
- **Async DB access** (`asyncpg` + SQLAlchemy's async engine) to increase
  concurrent request throughput under FastAPI's async event loop — the
  current implementation uses sync SQLAlchemy for simplicity/clarity.
- **Cursor signing** (HMAC) if cursors should be tamper-evident rather than
  merely opaque.

---

## 10. Interview explanation (live walkthrough)

> "The core problem is: browse 200k rows, newest first, and stay correct
> even while rows are being inserted or updated underneath you. The
> standard `OFFSET/LIMIT` approach fails both halves of that — it gets
> slower the deeper you page (Postgres still has to scan and discard every
> skipped row), and it's *wrong* under concurrent writes, because OFFSET is
> a position in the result set, and that position shifts whenever a row is
> inserted or removed ahead of it. You can end up seeing the same row twice
> or skipping one entirely.
>
> So instead I used keyset pagination: the cursor isn't a position, it's
> the actual sort key of the last row the client saw —
> `(updated_at, id)`, with `id` as a tiebreaker since timestamps alone
> aren't unique. Every subsequent page is just
> `WHERE (updated_at, id) < cursor ORDER BY updated_at DESC, id DESC LIMIT
> n` — a single sargable predicate that a composite index satisfies in one
> seek, so it's `O(limit)` no matter how deep you page, and it's correct
> under concurrent writes because the boundary is a value, not a count: new
> or updated rows always sort relative to that value, never silently
> shifting rows the client already saw.
>
> I built two composite indexes to back that: `(updated_at DESC, id DESC)`
> for the unfiltered browse, and `(category, updated_at DESC, id DESC)` so
> filtering by category still gets a single index scan instead of a sort
> step afterward. I verified the consistency property directly in tests —
> simulating an insert and an update mid-pagination and asserting no
> duplicate or missing IDs across the full page sequence."

---

## 11. Tests

```bash
pytest -v
```

| File                     | Covers                                                          |
|--------------------------|------------------------------------------------------------------|
| `tests/test_products.py` | Create, read, partial update, 404s, validation, `updated_at` bump |
| `tests/test_pagination.py` | Ordering, category filtering, cursor round-trip, invalid cursors, **no-duplicates/no-missing across full pagination**, **stability under concurrent insert**, **stability under concurrent update** |
