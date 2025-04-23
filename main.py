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
