import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents

app = FastAPI(title="Elevate Scripts API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Models for requests ---------
class StatusToggle(BaseModel):
    game: str  # vmp | cs2 | r6
    state: str  # detected | undetected
    note_fa: Optional[str] = None
    note_en: Optional[str] = None

class CartItem(BaseModel):
    slug: str
    qty: int = 1
    duration_label: Optional[str] = None  # for licenses: 1m | 3m

class CouponApply(BaseModel):
    code: str
    items: List[CartItem]

class CheckoutRequest(BaseModel):
    email: str
    address: Optional[str] = None
    items: List[CartItem]
    coupon: Optional[str] = None

# --------- Initial seed data helpers ---------
PRODUCTS = [
    {
        "type": "hardware",
        "slug": "elevate-v1",
        "title_fa": "Elevate v.1",
        "title_en": "Elevate v.1",
        "description_fa": "دستگاه سخت‌افزاری برای فعال‌سازی لایسنس و اتصال به HWID.",
        "description_en": "Hardware unit for license activation and HWID binding.",
        "requiresHardware": False,
        "price": 1_000_000,
        "images": ["/hardware.png"],
        "in_stock": True,
        "badge": "New",
    },
    {
        "type": "license",
        "slug": "vmp-license",
        "title_fa": "لایسنس VMP — ESP + Aimbot",
        "title_en": "VMP License — ESP + Aimbot",
        "description_fa": "نیازمند دستگاه Elevate v.1 — تحویل ایمیلی تا ۱ ساعت.",
        "description_en": "Requires Elevate v.1 — Delivery within 1 hour via email.",
        "game": "vmp",
        "durations": [
            {"label": "1m", "months": 1, "price": 3_000_000},
            {"label": "3m", "months": 3, "price": 8_000_000},
        ],
        "requiresHardware": True,
        "images": ["/vmp.png"],
        "in_stock": True,
        "badge": "Best Value",
    },
    {
        "type": "license",
        "slug": "cs2-license",
        "title_fa": "لایسنس CS2 — ESP + Aimbot",
        "title_en": "CS2 License — ESP + Aimbot",
        "description_fa": "نیازمند دستگاه Elevate v.1 — تحویل ایمیلی تا ۱ ساعت.",
        "description_en": "Requires Elevate v.1 — Delivery within 1 hour via email.",
        "game": "cs2",
        "durations": [
            {"label": "1m", "months": 1, "price": 3_000_000},
            {"label": "3m", "months": 3, "price": 8_000_000},
        ],
        "requiresHardware": True,
        "images": ["/cs2.png"],
        "in_stock": True,
    },
    {
        "type": "license",
        "slug": "r6-license",
        "title_fa": "لایسنس Rainbow Six — ESP + Aimbot",
        "title_en": "R6 License — ESP + Aimbot",
        "description_fa": "نیازمند دستگاه Elevate v.1 — تحویل ایمیلی تا ۱ ساعت.",
        "description_en": "Requires Elevate v.1 — Delivery within 1 hour via email.",
        "game": "r6",
        "durations": [
            {"label": "1m", "months": 1, "price": 3_000_000},
            {"label": "3m", "months": 3, "price": 8_000_000},
        ],
        "requiresHardware": True,
        "images": ["/r6.png"],
        "in_stock": True,
    },
]

STATUS_DEFAULTS = [
    {"game": "vmp", "state": "undetected", "updatedAt": datetime.utcnow()},
    {"game": "cs2", "state": "undetected", "updatedAt": datetime.utcnow()},
    {"game": "r6", "state": "undetected", "updatedAt": datetime.utcnow()},
]

FREE_SHIPPING_THRESHOLD = 8_000_000
FLAT_SHIPPING = 150_000

COUPONS = {
    "WELCOME10": 10,  # 10% off
}

@app.on_event("startup")
def seed_data():
    try:
        # Seed products if empty
        if db is not None and db["product"].count_documents({}) == 0:
            for p in PRODUCTS:
                create_document("product", p)
        # Seed status entries if empty (one per game)
        if db is not None:
            for s in STATUS_DEFAULTS:
                if db["statusentry"].count_documents({"game": s["game"]}) == 0:
                    create_document("statusentry", s)
    except Exception:
        pass

@app.get("/")
def root():
    return {"message": "Elevate Scripts API is running"}

@app.get("/api/products")
def list_products():
    if db is None:
        return {"items": PRODUCTS}
    items = get_documents("product")
    for i in items:
        i["_id"] = str(i["_id"])  # make JSON serializable
    return {"items": items}

@app.get("/api/status")
def get_status():
    if db is None:
        return {"entries": STATUS_DEFAULTS}
    entries = get_documents("statusentry")
    for e in entries:
        e["_id"] = str(e["_id"])  # make JSON serializable
    return {"entries": entries}

@app.post("/api/status/toggle")
def toggle_status(payload: StatusToggle):
    if payload.game not in {"vmp", "cs2", "r6"}:
        raise HTTPException(status_code=400, detail="Invalid game")
    if payload.state not in {"detected", "undetected"}:
        raise HTTPException(status_code=400, detail="Invalid state")

    entry = {
        "game": payload.game,
        "state": payload.state,
        "updatedAt": datetime.utcnow(),
        "note_fa": payload.note_fa,
        "note_en": payload.note_en,
    }
    if db is None:
        # No persistence but return the new state
        return {"updated": entry}
    # Upsert
    db["statusentry"].update_one({"game": payload.game}, {"$set": entry}, upsert=True)
    return {"updated": entry}

@app.post("/api/cart/calc")
def calc_cart(payload: CouponApply):
    items = payload.items
    # Price lookup from PRODUCTS or DB
    def item_price(item: CartItem) -> int:
        slug = item.slug
        source = PRODUCTS
        if db is not None:
            source = get_documents("product")
        prod = next((p for p in source if p.get("slug") == slug), None)
        if not prod:
            raise HTTPException(404, "Product not found")
        if prod["type"] == "hardware":
            return int(prod.get("price", 0)) * item.qty
        # license
        dur = next((d for d in prod.get("durations", []) if d.get("label") == item.duration_label), None)
        if not dur:
            raise HTTPException(400, "Invalid duration")
        return int(dur.get("price", 0)) * item.qty

    subtotal = sum(item_price(i) for i in items)
    discount_pct = COUPONS.get(payload.code.upper(), 0) if payload.code else 0
    discount = subtotal * discount_pct // 100
    after_discount = subtotal - discount
    shipping_fee = 0 if after_discount > FREE_SHIPPING_THRESHOLD else FLAT_SHIPPING
    total = after_discount + shipping_fee

    return {
        "subtotal": subtotal,
        "discount": discount,
        "shipping_fee": shipping_fee,
        "total": total,
        "free_shipping_threshold": FREE_SHIPPING_THRESHOLD,
        "currency": "IRT",
    }

@app.post("/api/checkout")
def checkout(req: CheckoutRequest):
    # This is a placeholder for local Iranian payment integration.
    # We create an order and return a mock payment URL/status.
    # Email sending of license will be handled after payment confirmation in real flow.
    calc = calc_cart(CouponApply(code=req.coupon or "", items=req.items))
    order_doc = {
        "email": req.email,
        "address": req.address,
        "items": [i.model_dump() for i in req.items],
        "subtotal": calc["subtotal"],
        "discount": calc["discount"],
        "shipping_fee": calc["shipping_fee"],
        "total": calc["total"],
        "coupon": req.coupon,
        "payment_status": "pending",
        "created_at": datetime.utcnow(),
    }
    if db is not None:
        oid = create_document("order", order_doc)
        order_doc["_id"] = oid
    return {
        "order": order_doc,
        "payment_gateway": {
            "provider": "LOCAL_IRT_PLACEHOLDER",
            "redirect_url": "https://example.com/pay/mock",
            "note": "Integrate local Iranian gateway here.",
        },
    }

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
