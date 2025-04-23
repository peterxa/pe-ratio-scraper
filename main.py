from fastapi import FastAPI
import yfinance as yf

app = FastAPI()

@app.get("/pe/{ticker}")
def get_pe_ratio(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        pe_ratio = stock.info.get("trailingPE")

        if pe_ratio is None:
            return {"ticker": ticker, "error": "P/E ratio no disponible"}

        return {"ticker": ticker, "pe_ratio": pe_ratio}
    
    except Exception as e:
        return {"error": str(e)}

@app.get("/dividend/{ticker}")
def get_dividend(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        dividend = stock.info.get("dividendRate")
        dividend_yield = stock.info.get("dividendYield")

        if dividend is None:
            return {"ticker": ticker, "error": "Dividendo no disponible"}

        return {
            "ticker": ticker,
            "dividend": dividend,
            "dividend_yield": f"{dividend_yield * 100:.2f}%" if dividend_yield else None
        }
    
    except Exception as e:
        return {"error": str(e)}
