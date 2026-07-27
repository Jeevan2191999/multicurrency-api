from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import requests
import uuid

app = FastAPI(title="Currency Platform")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database
engine = create_engine("sqlite:///./currency.db", connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    from_currency = Column(String)
    to_currency = Column(String)
    amount = Column(Float)
    converted_amount = Column(Float)
    rate = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

SUPPORTED = ["GBP", "USD", "EUR", "AED", "JPY", "CAD", "CHF", "SGD"]

def get_rates(base="GBP"):
    try:
        response = requests.get(
            f"https://api.exchangerate-api.com/v4/latest/{base}",
            timeout=5
        )
        data = response.json()
        return {k: v for k, v in data["rates"].items() if k in SUPPORTED}
    except Exception:
        fallback = {
            "GBP": {"USD": 1.27, "EUR": 1.17, "AED": 4.65, "JPY": 189.50, "CAD": 1.72, "CHF": 1.13, "SGD": 1.70},
            "USD": {"GBP": 0.79, "EUR": 0.92, "AED": 3.67, "JPY": 149.50, "CAD": 1.36, "CHF": 0.89, "SGD": 1.34},
        }
        return fallback.get(base, fallback["GBP"])

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    rates = get_rates("GBP")
    db = SessionLocal()
    transactions = db.query(Transaction).order_by(
        Transaction.created_at.desc()
    ).limit(10).all()
    db.close()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "rates": rates,
            "currencies": SUPPORTED,
            "transactions": transactions,
            "last_updated": datetime.utcnow().strftime("%d %b %Y, %H:%M UTC"),
            "result": None
        }
    )

@app.post("/convert", response_class=HTMLResponse)
async def convert(
    request: Request,
    from_currency: str = Form(...),
    to_currency: str = Form(...),
    amount: float = Form(...)
):
    rates = get_rates(from_currency)
    rate = rates.get(to_currency, 1.0)
    converted = round(amount * rate, 2)

    db = SessionLocal()
    transaction = Transaction(
        from_currency=from_currency,
        to_currency=to_currency,
        amount=amount,
        converted_amount=converted,
        rate=rate
    )
    db.add(transaction)
    db.commit()

    transactions = db.query(Transaction).order_by(
        Transaction.created_at.desc()
    ).limit(10).all()
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "rates": get_rates("GBP"),
            "currencies": SUPPORTED,
            "transactions": transactions,
            "last_updated": datetime.utcnow().strftime("%d %b %Y, %H:%M UTC"),
            "result": {
                "from": from_currency,
                "to": to_currency,
                "amount": amount,
                "converted": converted,
                "rate": rate
            }
        }
    )

@app.get("/api/rates/{base}")
async def api_rates(base: str):
    rates = get_rates(base.upper())
    return {
        "base": base.upper(),
        "rates": rates,
        "timestamp": datetime.utcnow().isoformat()
    }