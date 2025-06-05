# 📊 Stock Sentiment Tracker

A real-time stock sentiment analysis application that combines financial data with news sentiment analysis to provide comprehensive stock insights.

## 🚀 Features

### 📈 Real-time Stock Data
- **Multiple Data Sources**: Primary yfinance API with Yahoo Finance web scraping fallback
- **Comprehensive Metrics**: Current price, change, percentage change, volume, market cap
- **Reliable Data**: Automatic fallback ensures data availability even when primary sources fail

### 📰 News Sentiment Analysis
- **Multi-source News**: Aggregates headlines from Yahoo Finance and Google News
- **Advanced NLP**: Uses TextBlob for sentiment analysis with polarity scoring
- **Smart Filtering**: Removes duplicates and irrelevant headlines for accurate analysis

### ⚡ Performance & Reliability
- **Smart Caching**: 15-minute cache system reduces API calls and prevents rate limiting
- **Rate Limiting**: Built-in rate limiting with exponential backoff retry logic
- **Error Handling**: Comprehensive error handling with graceful degradation

### 🔍 Analysis Features
- **Single Stock Analysis**: Detailed analysis of individual stocks
- **Multi-Stock Comparison**: Compare up to 10 stocks simultaneously
- **Interactive Charts**: Visual correlation between price and sentiment (up to 20 stocks)
- **Sentiment Scoring**: Numerical sentiment scores with positive/negative/neutral classification

### 🌐 Web Interface
- **Dashboard**: Clean, intuitive web interface for easy stock analysis
- **Responsive Design**: Works on desktop and mobile devices
- **Multiple Views**: JSON API responses and HTML reports
- **Real-time Results**: Asynchronous processing for fast response times

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Data Sources**: yfinance, Yahoo Finance, Google News
- **NLP**: TextBlob for sentiment analysis
- **Web Scraping**: BeautifulSoup4, Requests
- **Frontend**: HTML5, CSS3, JavaScript
- **Templating**: Jinja2
- **Caching**: JSON file-based caching system

## 📋 Requirements

```
fastapi==0.104.1
uvicorn[standard]==0.24.0
beautifulsoup4==4.12.2
requests==2.31.0
yfinance==0.2.28
textblob==0.17.1
jinja2==3.1.2
python-multipart==0.0.6
```

## 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd stock-sentiment-tracker
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

5. **Access the dashboard**
   Open your browser and navigate to `http://localhost:8000/dashboard`

## 📚 API Endpoints

### Stock Analysis
- `GET /stock/{symbol}` - Get JSON analysis for a stock
- `GET /stock/{symbol}/html` - Get HTML report for a stock

### Multi-Stock Comparison
- `GET /compare?symbols=AAPL&symbols=GOOGL` - Compare multiple stocks (JSON)
- `GET /compare/html?symbols=AAPL&symbols=GOOGL` - Compare multiple stocks (HTML)

### Charts
- `GET /chart/html?symbols=AAPL&symbols=GOOGL` - Interactive price vs sentiment chart

### Cache Management
- `GET /cache/status` - View cache status and statistics
- `POST /cache/clear` - Clear expired cache entries

### Dashboard
- `GET /dashboard` - Main web interface
- `GET /` - API information

## 💡 Usage Examples

### Single Stock Analysis
```bash
curl http://localhost:8000/stock/AAPL
```

### Multi-Stock Comparison
```bash
curl "http://localhost:8000/compare?symbols=AAPL&symbols=GOOGL&symbols=TSLA"
```

### Popular Stock Combinations
- **Tech Giants**: AAPL, GOOGL, MSFT, AMZN
- **Auto Industry**: TSLA, F, GM, RIVN
- **Banking**: JPM, BAC, WFC

## 🏗️ Architecture

```
stock-sentiment-tracker/
├── main.py              # FastAPI application and routes
├── scraper.py           # Data collection and sentiment analysis
├── requirements.txt     # Python dependencies
├── templates/           # HTML templates
│   ├── dashboard.html   # Main dashboard interface
│   ├── stock_info.html  # Single stock report
│   ├── comparison.html  # Multi-stock comparison
│   ├── chart.html       # Interactive charts
│   └── error.html       # Error page
├── cache/               # Cached stock data (auto-generated)
└── venv/               # Virtual environment
```

## 🔧 Configuration

### Cache Settings
- **Duration**: 15 minutes (configurable in `scraper.py`)
- **Location**: `./cache/` directory
- **Format**: JSON files named by stock symbol

### Rate Limiting
- **Minimum Interval**: 1 second between requests
- **Retry Logic**: Exponential backoff with jitter
- **Max Retries**: 3 attempts for most operations

## 🚨 Error Handling

The application handles various error scenarios:
- **Invalid stock symbols**: Graceful error messages
- **Network failures**: Automatic retry with fallback data sources
- **Rate limiting**: Built-in delays and backoff strategies
- **Data unavailability**: Informative error responses

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## ⚠️ Disclaimer

This application is for educational and informational purposes only. Stock market data and sentiment analysis should not be used as the sole basis for investment decisions. Always consult with financial professionals before making investment choices.

## 🔮 Future Enhancements

- Historical sentiment tracking
- More news sources integration
- Advanced sentiment analysis models
- Real-time WebSocket updates
- Portfolio tracking features
- Technical indicator integration
