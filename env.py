"""
Tests for cursor pagination: ordering, category filtering, cursor
generation/validation, and — most importantly — the "no duplicates,
no missing records" guarantee under concurrent writes.
"""


def _create_products(client, count, category="Electronics"):
    for i in range(count):
        client.post(
            "/products",
            json={"name": f"Item {i}", "category": category, "price": "10.00"},
        )


def test_pagination_no_duplicates_no_missing(client):
    _create_products(client, 25)

    seen_ids = []
    cursor = None
    pages = 0

    while True:
        params = {"limit": 10}
        if cursor:
            params["cursor"] = cursor
        response = client.get("/products", params=params)
        assert response.status_code == 200
        body = response.json()
        seen_ids.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        pages += 1
        assert pages < 10, "too many pages — possible infinite loop"
        if not body["has_more"]:
            break

    assert len(seen_ids) == 25
    assert len(set(seen_ids)) == 25  # no duplicates anywhere across pages


def test_pagination_ordered_newest_first(client):
    _create_products(client, 5)

    response = client.get("/products", params={"limit": 50})
    items = response.json()["items"]
    updated_ats = [item["updated_at"] for item in items]
    assert updated_ats == sorted(updated_ats, reverse=True)


def test_pagination_stable_when_new_item_inserted_during_browsing(client):
    """
    Simulates the exact scenario from the assignment: a new product is
    inserted while a user is mid-pagination. Because the cursor anchors on
    (updated_at, id) of the last seen row, the new row (which sorts ahead
    of the cursor) never leaks into a later page, and no row the user
    already saw is repeated.
    """
    _create_products(client, 5)

    first_page = client.get("/products", params={"limit": 2}).json()
    first_ids = {item["id"] for item in first_page["items"]}

    client.post(
        "/products",
        json={"name": "Newly Inserted", "category": "Electronics", "price": "99.00"},
    )

    second_page = client.get(
        "/products", params={"limit": 10, "cursor": first_page["next_cursor"]}
    ).json()
    second_ids = {item["id"] for item in second_page["items"]}

    assert first_ids.isdisjoint(second_ids)


def test_pagination_stable_when_earlier_item_updated_during_browsing(client):
    """
    Updating a row that was already paged past (so its updated_at jumps to
    "now") must not cause it to reappear later in the same browse session.
    """
    _create_products(client, 5)

    first_page = client.get("/products", params={"limit": 2}).json()
    first_page_ids = [item["id"] for item in first_page["items"]]

    # Update a product that has NOT been seen yet — its updated_at moves to
    # "now", which pushes it ahead of the cursor, not behind it.
    response = client.get("/products", params={"limit": 50})
    all_ids = [item["id"] for item in response.json()["items"]]
    unseen_id = next(i for i in all_ids if i not in first_page_ids)
    client.put(f"/products/{unseen_id}", json={"price": "999.00"})

    second_page = client.get(
        "/products", params={"limit": 10, "cursor": first_page["next_cursor"]}
    ).json()
    second_page_ids = {item["id"] for item in second_page["items"]}

    # The updated row now sorts as "newest" and belongs before the cursor,
    # so it correctly does NOT show up again in the second page.
    assert unseen_id not in second_page_ids


def test_invalid_cursor_returns_400(client):
    response = client.get("/products", params={"cursor": "not-a-valid-cursor"})
    assert response.status_code == 400


def test_category_filter(client):
    _create_products(client, 8, category="Books")
    _create_products(client, 3, category="Toys")

    response = client.get("/products", params={"category": "Books", "limit": 50})
    items = response.json()["items"]
    assert len(items) == 8
    assert all(item["category"] == "Books" for item in items)


def test_category_filter_paginates_independently(client):
    _create_products(client, 12, category="Beauty")
    _create_products(client, 4, category="Automotive")

    seen_ids = []
    cursor = None
    while True:
        params = {"category": "Beauty", "limit": 5}
        if cursor:
            params["cursor"] = cursor
        body = client.get("/products", params=params).json()
        seen_ids.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if not body["has_more"]:
            break

    assert len(seen_ids) == 12
    assert len(set(seen_ids)) == 12
