# 🛒 Grocery Price Comparison Platform

A comprehensive grocery price comparison platform that scrapes multiple supermarket websites to help you find the best deals on groceries.

## 🏗️ Project Structure

```
scrapper/
├── 🛍️ grocery-api/       # Backend API service
├── 🖥️ grocery-frontend/   # React frontend application
```

## 🚀 Quick Start

### Prerequisites

Make sure you have the following installed:
- Node.js (v14 or higher)
- Python 3.8+
- Chrome/Chromium browser

### 🐍 Virtual Environment Setup

```bash
cd ./
source venv/bin/activate
```

## 🏃‍♂️ Running the Application

### 🖥️ Frontend Development Server
*Runs on port 5173*

```bash
cd grocery-frontend 
npm run dev
```

### 🔧 Backend API Server
*Runs on port 5002*

```bash
cd grocery-api 
pip install -r requirements.txt
python src/main.py
```

## 🌐 Browser Installation

### 🍎 macOS
```bash
# Using Homebrew
brew install --cask google-chrome
# or
brew install --cask chromium
```

### 🐧 Ubuntu/Debian
```bash
# Install Chromium
sudo apt update
sudo apt install chromium-browser
```

## 🏪 Individual Scrapers

### IGA Scraper Usage
```bash
cd iga/
pip install -r requirements.txt
python iga_scraper.py bread --sort price --page 2
```

## 🛠️ Features

- 🔍 Multi-store price comparison
- 📊 Real-time price scraping
- 🎨 Modern React frontend
- 🚀 Fast API backend
- 📱 Responsive design

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
