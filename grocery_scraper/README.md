# Grocery Scraper - Node.js Web Scraping Tool

A Node.js web scraping tool for Australian grocery stores including Woolworths, Coles, IGA, Harris Farm Markets, and ALDI Australia.

## Features

- **Multi-store Support**: Scrape products from 5 major Australian grocery retailers
- **Concurrent Scraping**: Search multiple stores simultaneously for faster results
- **Price Comparison**: Compare prices across different stores
- **Flexible Search**: Search specific stores or all stores at once
- **Command Line Interface**: Easy-to-use CLI for quick searches
- **Modular Design**: Each store has its own scraper module for easy maintenance

## Security

This project follows security best practices:
- ✅ **No known vulnerabilities** (as of 2024-07-31)
- ✅ **Latest dependencies**: Puppeteer 24.15.0+, Cheerio 1.1.2+
- ✅ **Regular security audits**: `npm audit` shows 0 vulnerabilities
- ✅ **Sandboxed execution**: Puppeteer runs in secure mode

See [SECURITY.md](SECURITY.md) for detailed security information.

## Installation

1. Clone or download this project
2. Install dependencies:
```bash
npm install
```

## Usage

### Command Line Interface

```bash
# Search all stores for a product
node index.js search "milk"

# Search a specific store
node index.js search "bread" woolworths

# Limit results
node index.js search "coffee" coles 10

# Get help
node index.js help
```

### Programmatic Usage

```javascript
const GroceryScraper = require('./index');

async function example() {
    const scraper = new GroceryScraper();
    
    try {
        // Search a single store
        const woolworthsResults = await scraper.scrapeStore('woolworths', 'milk', 10);
        console.log('Woolworths results:', woolworthsResults);
        
        // Search all stores
        const allResults = await scraper.scrapeAllStores('bread', 5);
        console.log('All stores results:', allResults);
        
        // Use utility functions
        const flatResults = scraper.flattenResults(allResults);
        const sortedByPrice = scraper.sortByPrice(flatResults);
        
    } finally {
        await scraper.closeAll();
    }
}
```

## Project Structure

```
grocery_scraper/
├── index.js              # Main application and CLI
├── package.json           # Project configuration
├── test.js               # Test suite
├── README.md             # This file
└── scrapers/             # Individual store scrapers
    ├── woolworths.js     # Woolworths scraper
    ├── coles.js          # Coles scraper
    ├── iga.js            # IGA scraper
    ├── harris.js         # Harris Farm Markets scraper
    └── aldi.js           # ALDI Australia scraper
```

## Supported Stores

| Store | Website | Status |
|-------|---------|--------|
| Woolworths | woolworths.com.au | ✅ Implemented |
| Coles | coles.com.au | ✅ Implemented |
| IGA | igashop.com.au | ✅ Implemented |
| Harris Farm Markets | harrisfarm.com.au | ✅ Implemented |
| ALDI Australia | aldi.com.au | ✅ Implemented |

## API Reference

### GroceryScraper Class

#### Methods

- `scrapeStore(storeName, query, maxResults)` - Search a specific store
- `scrapeAllStores(query, maxResults)` - Search all stores concurrently
- `getProductDetails(storeName, productUrl)` - Get detailed product information
- `closeAll()` - Close all browser instances
- `flattenResults(results)` - Convert store-grouped results to flat array
- `sortByPrice(products, ascending)` - Sort products by price
- `filterByStore(products, storeName)` - Filter products by store
- `searchInResults(products, searchTerm)` - Search within existing results

#### Product Data Structure

Each product object contains:
```javascript
{
    store: "Store Name",
    name: "Product Name",
    price: "$X.XX",
    unitPrice: "$X.XX / unit",
    imageUrl: "https://...",
    productUrl: "https://...",
    scraped_at: "2024-01-01T00:00:00.000Z"
}
```

## Technical Implementation

### Technologies Used

- **Puppeteer**: Headless Chrome automation for dynamic content
- **Cheerio**: Server-side jQuery implementation for HTML parsing
- **Node.js**: Runtime environment

### Scraping Strategy

1. **Dynamic Content Handling**: Uses Puppeteer to handle JavaScript-rendered content
2. **Robust Selectors**: Multiple fallback selectors for different page layouts
3. **Error Handling**: Graceful failure handling with detailed error messages
4. **Rate Limiting**: Built-in delays to avoid overwhelming servers
5. **Popup Handling**: Automatic detection and dismissal of popups

### Challenges and Limitations

#### Current Challenges

1. **Anti-Bot Measures**: Some websites implement sophisticated bot detection
2. **Dynamic Selectors**: Websites frequently change their HTML structure
3. **Rate Limiting**: Aggressive scraping may result in IP blocking
4. **JavaScript Dependencies**: Heavy reliance on client-side rendering

#### Recommendations for Production Use

1. **Proxy Rotation**: Use rotating proxies to avoid IP blocking
2. **User Agent Rotation**: Rotate user agents to appear more human-like
3. **Respect robots.txt**: Check and follow robots.txt guidelines
4. **Implement Delays**: Add random delays between requests
5. **Monitor Changes**: Regularly update selectors as websites change
6. **Legal Compliance**: Ensure compliance with website terms of service

## Testing

Run the test suite:
```bash
npm test
# or
node test.js
```

The test suite includes:
- Individual store scraping tests
- Multi-store concurrent scraping
- Utility function validation
- Error handling verification

## Development

### Adding New Stores

1. Create a new scraper file in the `scrapers/` directory
2. Implement the required methods: `searchProducts()`, `getProductDetails()`, `close()`
3. Add the scraper to the main `GroceryScraper` class
4. Update documentation and tests

### Updating Selectors

When websites change their structure:
1. Inspect the new HTML structure
2. Update the CSS selectors in the appropriate scraper
3. Test the changes
4. Update fallback selectors if needed

## Legal and Ethical Considerations

⚠️ **Important Notice**: This tool is for educational purposes only.

- **Respect Terms of Service**: Always check and comply with website terms of service
- **Rate Limiting**: Don't overwhelm servers with too many requests
- **robots.txt**: Respect robots.txt files
- **Data Usage**: Use scraped data responsibly and in accordance with applicable laws
- **Commercial Use**: Seek permission before using for commercial purposes

## Troubleshooting

### Common Issues

1. **No Results Found**
   - Check if selectors need updating
   - Verify website accessibility
   - Check for anti-bot measures

2. **Timeout Errors**
   - Increase timeout values
   - Check internet connection
   - Verify website is responsive

3. **Popup Issues**
   - Update popup selectors
   - Add new popup handling logic

### Debug Mode

Enable debug logging by setting environment variable:
```bash
DEBUG=true node index.js search milk
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Update documentation
6. Submit a pull request

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is provided "as is" without warranty of any kind. The authors are not responsible for any misuse of this tool or any consequences resulting from its use. Users are responsible for ensuring their use complies with applicable laws and website terms of service.

