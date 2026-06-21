"""
Pydantic schemas — the API's request/response contracts.

Kept separate from the SQLAlchemy models (app/models.py) on purpose:
the ORM model describes storage, these describe the wire format, and
the two are allowed to diverge (e.g. ProductUpdate makes every field
optional for partial updates).
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    price: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)


class ProductCreate(ProductBase):
    """Body for POST /products — every field required."""


class ProductUpdate(BaseModel):
    """Body for PUT /products/{id} — every field optional (partial update)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    price: Optional[Decimal] = Field(None, gt=0, max_digits=10, decimal_places=2)


class ProductOut(ProductBase):
    """A product as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProductPage(BaseModel):
    """Response envelope for GET /products."""

    items: List[ProductOut]
    next_cursor: Optional[str] = None
    has_more: bool
