"""
Database Schemas for Elevate Scripts

Each Pydantic model corresponds to a MongoDB collection with the collection
name equal to the lowercase class name.

Collections:
- product
- statusentry
- order
- license
- user
- rebindrequest
"""
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

Currency = Literal["IRR"]

class Duration(BaseModel):
    label: Literal["1m", "3m"]
    months: int = Field(..., ge=1)
    price: int = Field(..., ge=0, description="Price in IRT (Toman)")

class Product(BaseModel):
    type: Literal["hardware", "license"]
    slug: str
    title_fa: str
    title_en: str
    description_fa: Optional[str] = None
    description_en: Optional[str] = None
    game: Optional[Literal["vmp", "cs2", "r6"]] = None
    durations: Optional[List[Duration]] = None
    requiresHardware: bool = True
    price: Optional[int] = Field(None, ge=0, description="For hardware price in IRT")
    images: List[str] = []
    in_stock: bool = True
    badge: Optional[str] = None  # e.g., New, Best Value

class StatusEntry(BaseModel):
    game: Literal["vmp", "cs2", "r6"]
    state: Literal["detected", "undetected"] = "undetected"
    updatedAt: datetime
    note_fa: Optional[str] = None
    note_en: Optional[str] = None

class OrderItem(BaseModel):
    slug: str
    title: str
    type: Literal["hardware", "license"]
    duration_label: Optional[Literal["1m", "3m"]] = None
    qty: int = Field(1, ge=1)
    unit_price: int = Field(..., ge=0)
    total_price: int = Field(..., ge=0)

class Order(BaseModel):
    email: EmailStr
    address: Optional[str] = None
    items: List[OrderItem]
    subtotal: int
    discount: int = 0
    shipping_fee: int = 0
    total: int
    coupon: Optional[str] = None
    payment_status: Literal["pending", "paid", "failed"] = "pending"
    delivery_notes: Optional[str] = None

class License(BaseModel):
    email: EmailStr
    game: Literal["vmp", "cs2", "r6"]
    duration_label: Literal["1m", "3m"]
    key_masked: str
    status: Literal["active", "expired"] = "active"
    expiry: datetime
    hwid_masked: str = "****-****-****"

class User(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    address: Optional[str] = None

class RebindRequest(BaseModel):
    email: EmailStr
    license_key_masked: str
    reason: Optional[str] = None
    created_at: datetime
