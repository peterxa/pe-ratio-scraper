from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from cachetools import TTLCache, cached
import yfinance as yf
import requests
import os
import time

from yfinance.exceptions import YFRateLimitError

app = FastAPI(
    title="Stock API",
    description="API para consultar datos financieros como P/E ratio y dividendos desde distintas fuentes, optimizada para AWS Lambda.",
    version="2.2.0",
)


# === MODELOS DE RESPUESTA ===
class KeyIndicatorsResponse(BaseModel):
    ticker: str
    price: Optional[float]
    pe_ratio: Optional[float]
    dividend_yield: Optional[str]
    eps: Optional[float]
    market_cap: Optional[float]
    beta: Optional[float]
    rsi: Optional[float]
    sector: Optional[str]
    industry: Optional[str]
    longName: Optional[str]
    country: Optional[str]


class PEResponse(BaseModel):
    ticker: str = Field(..., example="AAPL")
    pe_ratio: Optional[float] = Field(None, example=28.5)


class DividendResponse(BaseModel):
    ticker: str = Field(..., example="MSFT")
    dividend: Optional[float] = Field(None, example=2.48)
    dividend_yield: Optional[str] = Field(None, example="1.02%")


# === DEPENDENCIAS Y CLAVES API ===
def get_api_keys():
    return {
        "finnhub_api_key": os.environ.get("FINNHUB_API_KEY"),
        "fmp_api_key": os.environ.get("FMP_API_KEY"),
    }


# === SERVICIO DE DATOS ===
class StockService:
    # Mantiene el cache entre invocaciones pero se limpia automáticamente al nuevo despliegue
    _cache = TTLCache(maxsize=200, ttl=600)  # 10 minutos de cache

    @staticmethod
    @cached(_cache)
    def fetch_yfinance_data(ticker: str, retries: int = 3, wait: int = 5) -> dict:
        ticker_obj = yf.Ticker(ticker)
        for i in range(retries):
            try:
                data = ticker_obj.get_info()
                if data:
                    return {
                        "currentPrice": data.get("currentPrice"),
                        "marketCap": data.get("marketCap"),
                        "trailingPE": data.get("trailingPE"),
                        "trailingEps": data.get("trailingEps"),
                        "beta": data.get("beta"),
                        "dividendRate": data.get("dividendRate"),
                        "dividendYield": data.get("dividendYield"),
                        "sector": data.get("sector"),
                        "industry": data.get("industry"),
                        "longName": data.get("longName"),
                        "country": data.get("country"),
                    }
            except YFRateLimitError:
                delay = (i + 1) * wait
                print(
                    f"[WARN] Rate limit alcanzado en yfinance para {ticker}, reintentando en {delay}s..."
                )
                time.sleep(delay)
            except Exception as e:
                print(f"[ERROR] yfinance fallo con {ticker}: {e}")
                break

        print(f"[FALLBACK] usando fast_info para {ticker}")
        fast = ticker_obj.fast_info
        return {
            "currentPrice": getattr(fast, "last_price", None),
            "marketCap": getattr(fast, "market_cap", None),
            "trailingPE": None,
            "trailingEps": None,
            "beta": None,
            "dividendRate": None,
            "dividendYield": None,
            "sector": None,
            "industry": None,
            "longName": None,
            "country": None,
        }

    @staticmethod
    @cached(_cache)
    def fetch_finnhub_data(ticker: str, api_key: str) -> dict:
        if not api_key:
            raise HTTPException(
                status_code=500, detail="Clave API de Finnhub no configurada."
            )
        url = f"https://finnhub.io/api/v1/stock/metric?symbol={ticker.upper()}&metric=all&token={api_key}"
        response = requests.get(url)
        if response.status_code != 200:
            raise HTTPException(
                status_code=502, detail=f"Error al consultar Finnhub: {response.text}"
            )
        return response.json()

    @staticmethod
    @cached(_cache)
    def fetch_fmp_ratios(ticker: str, api_key: str) -> list:
        if not api_key:
            raise HTTPException(
                status_code=500, detail="Clave API de FMP no configurada."
            )
        url = f"https://financialmodelingprep.com/api/v3/financial-ratios-ttm/{ticker.upper()}?apikey={api_key}"
        response = requests.get(url)
        if response.status_code != 200:
            raise HTTPException(
                status_code=502, detail=f"Error al consultar FMP: {response.text}"
            )
        return response.json()

    @staticmethod
    def get_pe_ratio(ticker: str, source: str, api_keys: dict) -> Optional[float]:
        ticker = ticker.upper()
        if source == "yfinance":
            data = StockService.fetch_yfinance_data(ticker)
            return data.get("trailingPE") or None
        elif source == "finnhub":
            data = StockService.fetch_finnhub_data(ticker, api_keys["finnhub_api_key"])
            return data.get("metric", {}).get("peBasicExclExtraTTM")
        elif source == "fmp":
            data = StockService.fetch_fmp_ratios(ticker, api_keys["fmp_api_key"])
            if data and isinstance(data, list):
                return data[0].get("priceEarningsRatioTTM")
            return None
        else:
            raise HTTPException(status_code=400, detail="Fuente no válida")

    @staticmethod
    def get_dividend_data(ticker: str, source: str, api_keys: dict) -> dict:
        ticker = ticker.upper()
        if source == "yfinance":
            info = StockService.fetch_yfinance_data(ticker)
            return {
                "dividend": info.get("dividendRate"),
                "dividend_yield": info.get("dividendYield"),
            }
        elif source == "finnhub":
            data = StockService.fetch_finnhub_data(ticker, api_keys["finnhub_api_key"])
            metric = data.get("metric", {})
            return {
                "dividend": metric.get("dividendsPerShareTTM"),
                "dividend_yield": metric.get("dividendYieldIndicatedAnnual"),
            }
        elif source == "fmp":
            data = StockService.fetch_fmp_ratios(ticker, api_keys["fmp_api_key"])
            if not data or not isinstance(data, list):
                return {"dividend": None, "dividend_yield": None}
            return {
                "dividend": data[0].get("dividendPerShareTTM"),
                "dividend_yield": data[0].get("dividendYieldTTM"),
            }
        else:
            raise HTTPException(status_code=400, detail="Fuente no válida")

    @staticmethod
    def get_key_indicators(ticker: str, source: str, api_keys: dict) -> dict:
        ticker = ticker.upper()
        if source == "yfinance":
            data = StockService.fetch_yfinance_data(ticker)
            dy = data.get("dividendYield")
            return {
                "ticker": ticker,
                "price": data.get("currentPrice"),
                "pe_ratio": data.get("trailingPE"),
                "dividend_yield": (
                    f"{(dy * 100):.2f}%" if isinstance(dy, (float, int)) else None
                ),
                "eps": data.get("trailingEps"),
                "market_cap": data.get("marketCap"),
                "beta": data.get("beta"),
                "rsi": None,
                "sector": data.get("sector"),
                "industry": data.get("industry"),
                "longName": data.get("longName"),
                "country": data.get("country"),
            }
        elif source == "finnhub":
            metric = StockService.fetch_finnhub_data(
                ticker, api_keys["finnhub_api_key"]
            ).get("metric", {})
            return {
                "ticker": ticker,
                "price": metric.get("closePrice"),
                "pe_ratio": metric.get("peBasicExclExtraTTM"),
                "dividend_yield": (
                    f"{metric.get('dividendYieldIndicatedAnnual', 0):.2%}"
                    if metric.get("dividendYieldIndicatedAnnual")
                    else None
                ),
                "eps": metric.get("epsExclExtraItemsTTM"),
                "market_cap": metric.get("marketCapitalization"),
                "beta": metric.get("beta"),
                "rsi": metric.get("rsi"),
                "sector": None,
                "industry": None,
                "longName": None,
                "country": None,
            }
        elif source == "fmp":
            data = StockService.fetch_fmp_ratios(ticker, api_keys["fmp_api_key"])
            if not data:
                raise HTTPException(
                    status_code=404, detail="Datos no disponibles en FMP"
                )
            row = data[0]
            dy = row.get("dividendYieldTTM")
            return {
                "ticker": ticker,
                "price": row.get("price"),
                "pe_ratio": row.get("priceEarningsRatioTTM"),
                "dividend_yield": f"{dy:.2%}" if isinstance(dy, (float, int)) else None,
                "eps": row.get("epsTTM"),
                "market_cap": row.get("marketCapTTM"),
                "beta": row.get("betaTTM"),
                "rsi": row.get("rsiTTM"),
                "sector": None,
                "industry": None,
                "longName": None,
                "country": None,
            }
        else:
            raise HTTPException(status_code=400, detail="Fuente no válida o sin datos")


# === MIDDLEWARE DE AUTO-LIMPIEZA DE CACHE ===
class CacheControl:
    load_time = time.time()
    cache_cleared = False


@app.middleware("http")
async def clear_cache_on_new_code(request, call_next):
    if not CacheControl.cache_cleared:
        try:
            StockService._cache.clear()
            CacheControl.cache_cleared = True
            print(
                f"[INIT] Cache limpiado al arrancar nuevo contenedor ({CacheControl.load_time})"
            )
        except Exception as e:
            print(f"[WARN] No se pudo limpiar cache: {e}")
    response = await call_next(request)
    return response


# === ENDPOINTS FASTAPI ===
@app.get("/pe/{ticker}", response_model=PEResponse)
def get_pe_ratio(
    ticker: str, source: str = "yfinance", api_keys: dict = Depends(get_api_keys)
):
    pe = StockService.get_pe_ratio(ticker, source, api_keys)
    return {"ticker": ticker.upper(), "pe_ratio": pe}


@app.get("/dividend/{ticker}", response_model=DividendResponse)
def get_dividend(
    ticker: str, source: str = "yfinance", api_keys: dict = Depends(get_api_keys)
):
    data = StockService.get_dividend_data(ticker, source, api_keys)
    yield_val = data.get("dividend_yield")
    yield_str = f"{yield_val:.2%}" if isinstance(yield_val, (float, int)) else None
    return {
        "ticker": ticker.upper(),
        "dividend": data.get("dividend"),
        "dividend_yield": yield_str,
    }


@app.get("/v2/key-indicators/{ticker}", response_model=KeyIndicatorsResponse)
def get_key_indicators(
    ticker: str, source: str = "yfinance", api_keys: dict = Depends(get_api_keys)
):
    return StockService.get_key_indicators(ticker, source, api_keys)
