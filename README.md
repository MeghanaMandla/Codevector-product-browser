"""
ORM model for the `products` table.

Column choices map directly to the assignment spec:
- id: BIGSERIAL-equivalent primary key (BigInteger + autoincrement).
- category: indexed for fast equality filtering.
- updated_at: server-side default AND onupdate, so "updated_at must change
  on update" is enforced by the database itself, not just application code.
"""
from sqlalchemy import BigInteger, Column, DateTime, Numeric, String
from sqlalchemy.sql import func

from .database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Product id={self.id} name={self.name!r} category={self.category!r}>"
