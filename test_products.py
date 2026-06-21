"""
Seeds the products table with ~200,000 realistic rows for load-testing
pagination.

Usage:
    python scripts/seed_products.py
    python scripts/seed_products.py --total 50000 --batch-size 2000

Speed strategy:
- Generate rows in Python, but never insert one row at a time.
- Use SQLAlchemy Core's `insert(Table)` executed with a list of dicts:
  this lets the DBAPI driver (psycopg2) batch the statement into a single
  multi-row INSERT per chunk instead of round-tripping per row.
- Wrap the whole run in one transaction (`engine.begin()`), since 200k
  individually-committed inserts is the single biggest source of slowness.
"""
import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, insert  # noqa: E402

from app.config import settings  # noqa: E402
from app.models import Product  # noqa: E402

CATEGORIES = [
    "Electronics",
    "Fashion",
    "Books",
    "Sports",
    "Home",
    "Toys",
    "Beauty",
    "Automotive",
    "Grocery",
    "Health",
]

ADJECTIVES = [
    "Premium", "Classic", "Pro", "Essential", "Compact",
    "Deluxe", "Eco", "Smart", "Vintage", "Ultra",
]

NOUNS = {
    "Electronics": ["Headphones", "Charger", "Speaker", "Monitor", "Router", "Webcam"],
    "Fashion": ["Jacket", "Sneakers", "Jeans", "Hat", "Scarf", "Backpack"],
    "Books": ["Novel", "Cookbook", "Journal", "Biography", "Atlas", "Guide"],
    "Sports": ["Racket", "Helmet", "Jersey", "Treadmill", "Dumbbell", "Yoga Mat"],
    "Home": ["Lamp", "Sofa", "Rug", "Blender", "Mirror", "Shelf"],
    "Toys": ["Puzzle", "Drone", "Action Figure", "Board Game", "Lego Set", "Doll"],
    "Beauty": ["Serum", "Lipstick", "Shampoo", "Moisturizer", "Perfume", "Brush Set"],
    "Automotive": ["Dash Cam", "Floor Mat", "Car Charger", "Tire Gauge", "Seat Cover", "Wax Kit"],
    "Grocery": ["Coffee Beans", "Olive Oil", "Granola", "Honey", "Pasta", "Tea Set"],
    "Health": ["Vitamin Pack", "Thermometer", "Massager", "First Aid Kit", "Scale", "Inhaler"],
}


def random_timestamp(days_back: int = 730) -> datetime:
    delta = timedelta(days=random.randint(0, days_back), seconds=random.randint(0, 86_400))
    return datetime.utcnow() - delta


def generate_batch(start_index: int, size: int) -> list[dict]:
    rows = []
    for i in range(size):
        category = random.choice(CATEGORIES)
        name = f"{random.choice(ADJECTIVES)} {random.choice(NOUNS[category])} #{start_index + i}"
        created = random_timestamp()
        # ~30% of seeded products simulate having been edited after creation,
        # so updated_at isn't trivially identical to created_at for everyone.
        updated = (
            created + timedelta(seconds=random.randint(0, 3600 * 24 * 30))
            if random.random() < 0.3
            else created
        )
        rows.append(
            {
                "name": name,
                "category": category,
                "price": round(random.uniform(100, 10000), 2),
                "created_at": created,
                "updated_at": updated,
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Seed the products table.")
    parser.add_argument("--total", type=int, default=200_000, help="Total rows to insert")
    parser.add_argument("--batch-size", type=int, default=5_000, help="Rows per INSERT batch")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)

    engine = create_engine(settings.database_url)
    start = time.time()
    inserted = 0

    with engine.begin() as conn:
        for batch_start in range(0, args.total, args.batch_size):
            batch_size = min(args.batch_size, args.total - batch_start)
            rows = generate_batch(batch_start, batch_size)
            conn.execute(insert(Product.__table__), rows)
            inserted += batch_size
            elapsed = time.time() - start
            print(f"Inserted {inserted:,}/{args.total:,} ({elapsed:.1f}s elapsed)")

    total_elapsed = time.time() - start
    print(f"\nDone. Seeded {inserted:,} products in {total_elapsed:.1f}s "
          f"({inserted / total_elapsed:,.0f} rows/sec).")


if __name__ == "__main__":
    main()
