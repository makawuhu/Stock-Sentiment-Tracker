from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List
import logging
import asyncio
from scraper import get_stock_sentiment, StockSentimentError, stock_cache

app = FastAPI(title="Stock Sentiment Tracker", version="1.0.0")
templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/")
async def root():
    return {"message": "Stock Sentiment Tracker API"}

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard with search interface"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request
    })

@app.get("/stock/{symbol}")
async def get_stock_info(symbol: str):
    try:
        logger.info(f"Fetching stock info for {symbol}")
        result = await get_stock_sentiment(symbol.upper())
        return result
    except StockSentimentError as e:
        logger.error(f"Error fetching stock info for {symbol}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/stock/{symbol}/html", response_class=HTMLResponse)
async def get_stock_info_html(request: Request, symbol: str):
    try:
        result = await get_stock_sentiment(symbol.upper())
        return templates.TemplateResponse("stock_info.html", {
            "request": request,
            "symbol": symbol.upper(),
            "data": result
        })
    except StockSentimentError as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e)
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Internal server error"
        })

@app.get("/compare")
async def compare_stocks(symbols: List[str] = Query(..., description="List of stock symbols to compare")):
    """Compare sentiment analysis across multiple stocks"""
    if len(symbols) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 stocks allowed for comparison")
    
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="At least 2 stocks required for comparison")
    
    results = []
    errors = []
    
    async def get_stock_data(symbol: str):
        try:
            return await get_stock_sentiment(symbol.upper())
        except StockSentimentError as e:
            errors.append({"symbol": symbol.upper(), "error": str(e)})
            return None
    
    tasks = [get_stock_data(symbol) for symbol in symbols]
    stock_data = await asyncio.gather(*tasks, return_exceptions=True)
    
    for data in stock_data:
        if data is not None and not isinstance(data, Exception):
            results.append(data)
    
    if not results:
        raise HTTPException(status_code=400, detail="No valid stock data could be retrieved")
    
    comparison = {
        "stocks": results,
        "errors": errors,
        "summary": {
            "total_requested": len(symbols),
            "successful": len(results),
            "failed": len(errors)
        }
    }
    
    return comparison

@app.get("/compare/html", response_class=HTMLResponse)
async def compare_stocks_html(request: Request, symbols: List[str] = Query(..., description="List of stock symbols to compare")):
    """HTML view for stock comparison"""
    try:
        comparison_data = await compare_stocks(symbols)
        return templates.TemplateResponse("comparison.html", {
            "request": request,
            "data": comparison_data,
            "symbols": [s.upper() for s in symbols]
        })
    except HTTPException as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": e.detail
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Internal server error"
        })

@app.post("/cache/clear")
async def clear_cache():
    """Clear expired cache entries"""
    stock_cache.clear_expired()
    return {"message": "Expired cache entries cleared"}

@app.get("/cache/status")
async def cache_status():
    """Get cache status information"""
    import os
    cache_files = []
    if os.path.exists(stock_cache.cache_dir):
        for filename in os.listdir(stock_cache.cache_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(stock_cache.cache_dir, filename)
                stat = os.stat(filepath)
                cache_files.append({
                    "symbol": filename.replace('.json', ''),
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime
                })
    
    return {
        "cache_directory": stock_cache.cache_dir,
        "total_cached_symbols": len(cache_files),
        "cached_symbols": cache_files
    }

@app.get("/chart/html", response_class=HTMLResponse)
async def chart_view(request: Request, symbols: List[str] = Query(..., description="List of stock symbols for chart")):
    """Chart view showing price vs sentiment correlation"""
    try:
        if len(symbols) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 stocks allowed for chart")
        
        if len(symbols) < 2:
            raise HTTPException(status_code=400, detail="At least 2 stocks required for chart")
        
        # Get data for all symbols
        chart_data = []
        errors = []
        
        async def get_chart_data(symbol: str):
            try:
                data = await get_stock_sentiment(symbol.upper())
                return {
                    "symbol": data["symbol"],
                    "price": data["price_data"]["current_price"],
                    "change_percent": data["price_data"]["change_percent"],
                    "sentiment_score": data["sentiment_analysis"]["sentiment_score"],
                    "sentiment_label": data["sentiment_analysis"]["overall_sentiment"],
                    "company_name": data["price_data"]["company_name"]
                }
            except StockSentimentError as e:
                errors.append({"symbol": symbol.upper(), "error": str(e)})
                return None
        
        tasks = [get_chart_data(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if result is not None and not isinstance(result, Exception):
                chart_data.append(result)
        
        if not chart_data:
            raise HTTPException(status_code=400, detail="No valid stock data could be retrieved for chart")
        
        return templates.TemplateResponse("chart.html", {
            "request": request,
            "chart_data": chart_data,
            "errors": errors,
            "symbols": [s.upper() for s in symbols]
        })
    
    except HTTPException:
        raise
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Internal server error"
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)