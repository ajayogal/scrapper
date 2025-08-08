# Production Deployment Guide

## 🚀 Production Fix Summary

The "File is not defined" error has been resolved by fixing Node.js package compatibility issues.

## ✅ Fixed Issues

1. **Cheerio Version Compatibility**: Updated from `^1.1.2` to `1.0.0-rc.12`
2. **Puppeteer Version**: Downgraded from `^24.15.0` to `^19.11.1`
3. **Production Path Resolution**: Added proper fallback paths for production environment

## 📋 Deployment Steps

### 1. Update Dependencies in Production

```bash
cd /home/ec2-user/apps/scrapper/grocery-api/grocery_scraper
npm install
```

### 2. Verify Node.js Scraper Works

```bash
# Test the scraper directly
node index.js search milk --json

# Should return ~150 results from IGA, ALDI, and Harris Farm
```

### 3. Restart Your PM2 Services

```bash
pm2 restart grocery-api-flask
pm2 logs grocery-api-flask --lines 20
```

### 4. Test API Endpoints

```bash
# Health check
curl -X GET "http://localhost:5002/api/grocery/health"

# Search test
curl -X POST "http://localhost:5002/api/grocery/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "milk", "store": "aldi", "perPage": 5}'
```

## 🔧 Package Versions That Work

The following versions are compatible with older Node.js environments:

```json
{
  "dependencies": {
    "axios": "^1.6.0",
    "cheerio": "1.0.0-rc.12",  // Fixed: was ^1.1.2
    "node-fetch": "^2.7.0",
    "puppeteer": "^19.11.1"    // Fixed: was ^24.15.0
  }
}
```

## 🎯 Expected Results

After deployment, you should see:

- ✅ Node.js scraper works without "File is not defined" errors
- ✅ API returns real product data (150+ results for "milk")
- ✅ Both Python and Node.js scrapers available as fallbacks
- ✅ Enhanced logging for debugging

## 🐛 If Issues Persist

1. **Check Node.js Version**: Ensure Node.js >= 14.0.0
2. **Clear node_modules**: `rm -rf node_modules && npm install`
3. **Check logs**: `pm2 logs grocery-api-flask`
4. **Test scraper directly**: `node index.js search test --json`

## 📊 Test Commands

```bash
# Test Python scrapers (should work)
curl -X POST "http://localhost:5002/api/grocery/test-scraper" \
  -H "Content-Type: application/json" \
  -d '{"query": "milk", "use_python": true}'

# Test Node.js scraper (should work after fix)
curl -X POST "http://localhost:5002/api/grocery/test-scraper" \
  -H "Content-Type: application/json" \
  -d '{"query": "milk", "use_python": false}'
```

## ✨ Production Path Resolution

The API now checks these paths in order:

1. `/home/ec2-user/apps/scrapper/grocery-api/grocery_scraper` (your production path)
2. `../grocery_scraper` (relative path)
3. `./grocery_scraper` (current directory)
4. `/app/grocery_scraper` (common Docker path)

This ensures compatibility across different deployment environments.
