from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional
from cachetools import TTLCache, cached
import yfinance as yf

app = FastAPI(
    title="Stock API",
    description="API para consultar datos financieros como P/E ratio y dividendos.",
    version="1.0.0",
)

# === MODELOS DE RESPUESTA ===


class PEResponse(BaseModel):
    ticker: str = Field(..., example="AAPL")
    pe_ratio: Optional[float] = Field(None, example=28.5)
    error: Optional[str] = Field(None, example="P/E ratio no disponible")


class DividendResponse(BaseModel):
    ticker: str = Field(..., example="MSFT")
    dividend: Optional[float] = Field(None, example=2.48)
    dividend_yield: Optional[str] = Field(None, example="1.02%")
    error: Optional[str] = Field(None, example="Dividendo no disponible")


# === CACHÉ COMPLETO PARA DATOS DEL TICKER ===
ticker_cache = TTLCache(maxsize=100, ttl=600)


@cached(ticker_cache)
def fetch_full_ticker_data(ticker: str):
    stock = yf.Ticker(ticker)
    return {
        "info": stock.info,
        "recommendations": stock.recommendations,
        "history": stock.history(period="10y", interval="1mo", auto_adjust=True),
        "calendar": stock.calendar,
    }


# === ENDPOINT P/E ===
@app.get("/pe/{ticker}", response_model=PEResponse)
def get_pe_ratio(ticker: str):
    try:
        data = fetch_full_ticker_data(ticker)
        pe_ratio = data["info"].get("trailingPE")

        if pe_ratio is None:
            return {"ticker": ticker, "error": "P/E ratio no disponible"}

        return {"ticker": ticker, "pe_ratio": pe_ratio}

    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


# === ENDPOINT DIVIDENDOS ===
@app.get("/dividend/{ticker}", response_model=DividendResponse)
def get_dividend(ticker: str):
    try:
        data = fetch_full_ticker_data(ticker)
        info = data["info"]
        dividend = info.get("dividendRate")
        dividend_yield = info.get("dividendYield")

        # Datos extra para desarrollo (puedes comentar si no quieres que se impriman)
        print(f"📈 Precio actual: {info.get('currentPrice')}")
        print(f"📊 PER: {info.get('trailingPE')}")
        print(f"💰 Dividendo por acción: {dividend}")
        print(f"💸 Rendimiento del dividendo: {dividend_yield}")
        print(f"🏢 Sector: {info.get('sector')}")
        # print("\n🧠 Recomendaciones:")
        # print(
        #    data["recommendations"].tail()
        #    if data["recommendations"] is not None
        #    else "N/A"
        # )
        # print("\n📊 Historial:")
        # print(data["history"])
        # print("\n📅 Calendario:")
        # print(data["calendar"])

        if dividend is None:
            return {"ticker": ticker, "error": "Dividendo no disponible"}

        return {
            "ticker": ticker,
            "dividend": dividend,
            "dividend_yield": f"{dividend_yield * 100:.2f}%"
            if dividend_yield
            else None,
        }

    except Exception as e:
        return {"ticker": ticker, "error": str(e)}
