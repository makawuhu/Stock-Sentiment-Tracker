import requests
import yfinance as yf
from bs4 import BeautifulSoup
from textblob import TextBlob
import logging
from typing import Dict, List, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
import random
from functools import wraps
import json
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StockSentimentError(Exception):
    pass

# Rate limiting configuration
LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 1.0  # Minimum 1 second between requests

# Cache configuration
CACHE_DIR = "cache"
CACHE_DURATION = timedelta(minutes=15)  # Cache for 15 minutes

class StockDataCache:
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def _get_cache_filepath(self, symbol: str) -> str:
        return os.path.join(self.cache_dir, f"{symbol.upper()}.json")
    
    def get(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached data for a symbol if it exists and is not expired"""
        cache_file = self._get_cache_filepath(symbol)
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is expired
            cached_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cached_time > CACHE_DURATION:
                logger.info(f"Cache expired for {symbol}, removing cache file")
                os.remove(cache_file)
                return None
            
            logger.info(f"Using cached data for {symbol}")
            return cache_data['data']
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid cache file for {symbol}: {str(e)}")
            try:
                os.remove(cache_file)
            except:
                pass
            return None
    
    def set(self, symbol: str, data: Dict[str, Any]) -> None:
        """Cache data for a symbol"""
        cache_file = self._get_cache_filepath(symbol)
        
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"Cached data for {symbol}")
        except Exception as e:
            logger.error(f"Failed to cache data for {symbol}: {str(e)}")
    
    def clear_expired(self) -> None:
        """Remove all expired cache files"""
        if not os.path.exists(self.cache_dir):
            return
        
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.cache_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        cache_data = json.load(f)
                    
                    cached_time = datetime.fromisoformat(cache_data['timestamp'])
                    if datetime.now() - cached_time > CACHE_DURATION:
                        os.remove(filepath)
                        logger.info(f"Removed expired cache file: {filename}")
                        
                except Exception as e:
                    logger.warning(f"Error processing cache file {filename}: {str(e)}")

# Global cache instance
stock_cache = StockDataCache()

def rate_limit(func):
    """Decorator to add rate limiting to API calls"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        global LAST_REQUEST_TIME
        current_time = time.time()
        time_since_last = current_time - LAST_REQUEST_TIME
        
        if time_since_last < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - time_since_last + random.uniform(0.1, 0.5)
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        LAST_REQUEST_TIME = time.time()
        return func(*args, **kwargs)
    return wrapper

def retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0):
    """Decorator to add exponential backoff retry logic"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Don't retry on certain errors
                    if "404" in str(e) or "invalid symbol" in str(e).lower():
                        raise e
                    
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise e
                    
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0.1, 0.3) * delay
                    total_delay = delay + jitter
                    
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. Retrying in {total_delay:.2f}s")
                    time.sleep(total_delay)
            
            raise last_exception
        return wrapper
    return decorator

@rate_limit
@retry_with_backoff(max_retries=3, base_delay=1.0)
def get_stock_price_yfinance(symbol: str) -> Dict[str, Any]:
    """Get stock price using yfinance with rate limiting and retry logic"""
    ticker = yf.Ticker(symbol)
    
    hist = ticker.history(period="1d")
    if hist.empty:
        raise StockSentimentError(f"No price data found for symbol {symbol}, symbol may be delisted or blocked")
    
    latest = hist.iloc[-1]
    fast_info = getattr(ticker, "fast_info", {})
    
    # Use fast_info for more reliable data, fallback to calculated values
    current_price = fast_info.get("lastPrice") or float(latest["Close"])
    previous_close = fast_info.get("previousClose") or float(latest["Close"])
    
    change = current_price - previous_close
    change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
    
    # Get company name from fast_info or fallback to info
    company_name = symbol
    try:
        info = ticker.info
        company_name = info.get('longName', symbol)
    except:
        pass
    
    return {
        "current_price": round(current_price, 2),
        "previous_close": round(previous_close, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "company_name": company_name,
        "market_cap": fast_info.get("marketCap"),
        "open": float(latest["Open"]),
        "high": float(latest["High"]),
        "low": float(latest["Low"]),
        "volume": int(latest["Volume"]),
        "timestamp": latest.name.isoformat()
    }

@rate_limit
@retry_with_backoff(max_retries=2, base_delay=0.5)
def get_stock_price_yahoo_finance(symbol: str) -> Dict[str, Any]:
    """Alternative data source: scrape Yahoo Finance directly"""
    url = f"https://finance.yahoo.com/quote/{symbol}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Try multiple methods to find price elements
    price_elem = soup.find('fin-streamer', {'data-symbol': symbol, 'data-field': 'regularMarketPrice'})
    
    if not price_elem:
        # Try alternative selectors
        price_elem = soup.find('span', {'data-reactid': lambda x: x and 'price' in str(x)})
    
    if not price_elem:
        # Look for price in common span classes
        price_elem = soup.find('span', class_=lambda x: x and any(cls in x for cls in ['price', 'Fw(b)', 'regularMarketPrice']))
    
    if not price_elem:
        # Look for fin-streamer with data-test attribute
        price_elem = soup.find('fin-streamer', {'data-test': 'qsp-price'})
    
    if not price_elem:
        # Last resort: look for any element with price-like text pattern
        import re
        price_pattern = re.compile(r'\$?\d+\.\d{2}')
        price_spans = soup.find_all('span')
        for span in price_spans:
            text = span.get_text().strip()
            if price_pattern.match(text.replace('$', '').replace(',', '')):
                price_elem = span
                break
    
    if not price_elem:
        raise StockSentimentError(f"Could not find price data for {symbol} on Yahoo Finance")
    
    price_text = price_elem.get_text().replace(',', '').replace('$', '').strip()
    current_price = float(price_text)
    
    # Try to find change elements
    change_elem = soup.find('fin-streamer', {'data-symbol': symbol, 'data-field': 'regularMarketChange'})
    change_percent_elem = soup.find('fin-streamer', {'data-symbol': symbol, 'data-field': 'regularMarketChangePercent'})
    
    change = 0.0
    change_percent = 0.0
    
    if change_elem:
        try:
            change = float(change_elem.get_text().replace(',', '').replace('+', ''))
        except ValueError:
            pass
    
    if change_percent_elem:
        try:
            change_percent_text = change_percent_elem.get_text().replace('(', '').replace(')', '').replace('%', '').replace('+', '')
            change_percent = float(change_percent_text)
        except ValueError:
            pass
    
    previous_close = current_price - change
    
    # Try to find company name
    company_name = symbol
    name_elem = soup.find('h1', {'data-reactid': lambda x: x and 'title' in str(x)}) or soup.find('h1')
    if name_elem:
        company_name = name_elem.get_text().split('(')[0].strip()
    
    return {
        "current_price": round(current_price, 2),
        "previous_close": round(previous_close, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "company_name": company_name
    }

def get_stock_price(symbol: str) -> Dict[str, Any]:
    """Get stock price with fallback to alternative data source"""
    try:
        logger.info(f"Attempting to fetch price for {symbol} using yfinance")
        return get_stock_price_yfinance(symbol)
    except Exception as e:
        logger.warning(f"yfinance failed for {symbol}: {str(e)}. Trying alternative source.")
        try:
            logger.info(f"Attempting to fetch price for {symbol} using Yahoo Finance scraping")
            return get_stock_price_yahoo_finance(symbol)
        except Exception as e2:
            logger.error(f"All price sources failed for {symbol}. yfinance: {str(e)}, Yahoo scraping: {str(e2)}")
            raise StockSentimentError(f"Failed to fetch price data for {symbol} from all sources")

@rate_limit
@retry_with_backoff(max_retries=2, base_delay=0.5)
def scrape_yahoo_finance_news(symbol: str) -> List[str]:
    try:
        url = f"https://finance.yahoo.com/quote/{symbol}/news"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        headlines = []
        
        news_items = soup.find_all(['h3', 'h4'], class_=lambda x: x and 'headline' in x.lower())
        for item in news_items[:10]:
            text = item.get_text(strip=True)
            if text and len(text) > 10:
                headlines.append(text)
        
        if not headlines:
            news_links = soup.find_all('a')
            for link in news_links:
                text = link.get_text(strip=True)
                if text and len(text) > 20 and any(keyword in text.lower() for keyword in [symbol.lower(), 'stock', 'shares']):
                    headlines.append(text)
                    if len(headlines) >= 5:
                        break
        
        return headlines[:10] if headlines else []
        
    except requests.RequestException as e:
        logger.error(f"Network error scraping news for {symbol}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error scraping news for {symbol}: {str(e)}")
        return []

@rate_limit
@retry_with_backoff(max_retries=2, base_delay=0.5)
def scrape_google_news(symbol: str) -> List[str]:
    try:
        url = f"https://news.google.com/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US%3Aen"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        headlines = []
        
        articles = soup.find_all('article')
        for article in articles[:10]:
            title_elem = article.find('h3') or article.find('h4')
            if title_elem:
                text = title_elem.get_text(strip=True)
                if text and len(text) > 10:
                    headlines.append(text)
        
        return headlines
        
    except requests.RequestException as e:
        logger.error(f"Network error scraping Google news for {symbol}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error scraping Google news for {symbol}: {str(e)}")
        return []

def get_news_headlines(symbol: str) -> List[str]:
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            yahoo_future = executor.submit(scrape_yahoo_finance_news, symbol)
            google_future = executor.submit(scrape_google_news, symbol)
            
            yahoo_headlines = yahoo_future.result()
            google_headlines = google_future.result()
        
        all_headlines = yahoo_headlines + google_headlines
        unique_headlines = list(dict.fromkeys(all_headlines))
        
        if not unique_headlines:
            logger.warning(f"No news headlines found for {symbol}")
            raise StockSentimentError(f"No recent news articles found for stock symbol {symbol}. This could indicate an invalid symbol or lack of news coverage.")
            
        return unique_headlines[:15]
        
    except StockSentimentError:
        raise
    except Exception as e:
        logger.error(f"Error getting news headlines for {symbol}: {str(e)}")
        raise StockSentimentError(f"Failed to fetch news for {symbol}: {str(e)}")

def analyze_sentiment(headlines: List[str]) -> Dict[str, Any]:
    if not headlines or headlines == [f"No recent news found for {headlines[0].split()[-1]}"]:
        return {
            "overall_sentiment": "neutral",
            "sentiment_score": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 1
        }
    
    sentiments = []
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    
    for headline in headlines:
        try:
            blob = TextBlob(headline)
            polarity = blob.sentiment.polarity
            sentiments.append(polarity)
            
            if polarity > 0.1:
                positive_count += 1
            elif polarity < -0.1:
                negative_count += 1
            else:
                neutral_count += 1
        except Exception as e:
            logger.error(f"Error analyzing sentiment for headline: {headline}, error: {str(e)}")
            neutral_count += 1
    
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
    
    if avg_sentiment > 0.1:
        overall_sentiment = "positive"
    elif avg_sentiment < -0.1:
        overall_sentiment = "negative"
    else:
        overall_sentiment = "neutral"
    
    return {
        "overall_sentiment": overall_sentiment,
        "sentiment_score": round(avg_sentiment, 3),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count
    }

async def get_stock_sentiment(symbol: str) -> Dict[str, Any]:
    # Check cache first
    cached_data = stock_cache.get(symbol)
    if cached_data:
        return cached_data
    
    try:
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor() as executor:
            price_future = loop.run_in_executor(executor, get_stock_price, symbol)
            news_future = loop.run_in_executor(executor, get_news_headlines, symbol)
            
            price_data = await price_future
            headlines = await news_future
        
        sentiment_data = analyze_sentiment(headlines)
        
        result = {
            "symbol": symbol,
            "price_data": price_data,
            "news_headlines": headlines,
            "sentiment_analysis": sentiment_data,
            "total_articles": len(headlines)
        }
        
        # Cache the result
        stock_cache.set(symbol, result)
        
        return result
        
    except StockSentimentError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_stock_sentiment for {symbol}: {str(e)}")
        raise StockSentimentError(f"Failed to analyze sentiment for {symbol}")