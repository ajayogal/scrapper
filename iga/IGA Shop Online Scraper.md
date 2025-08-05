# IGA Shop Online Scraper

A comprehensive web scraper for iga.com.au (IGA Shop Online) that extracts product details including image URLs, names, prices, and discount information. The scraper provides functionality to search products and sort by price or discount availability.

## Features

- **Product Information Extraction**: Extracts product name, price, image URL, and discount information
- **Search Functionality**: Search for products using any query term
- **Multi-page Scraping**: Scrape multiple pages of search results
- **Sorting Options**: Sort products by price (ascending/descending) or discount availability
- **Filtering**: Filter to show only discounted products
- **Export Options**: Save results to JSON format
- **Command-line Interface**: Easy-to-use CLI with various options

## Requirements

- Python 3.7+
- Chrome/Chromium browser
- ChromeDriver (automatically managed by webdriver-manager)

## Installation

1. Clone or download the scraper files
2. Install required dependencies:

```bash
pip install selenium beautifulsoup4 webdriver-manager
```

3. Install Chrome or Chromium browser:

**macOS:**
```bash
# Using Homebrew
brew install --cask google-chrome
# or
brew install --cask chromium
```

**Ubuntu/Debian:**
```bash
# Install Chromium
sudo apt update
sudo apt install chromium-browser

# Or install Google Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update
sudo apt install google-chrome-stable
```

**CentOS/RHEL/Fedora:**
```bash
# Install Chromium
sudo dnf install chromium

# Or install Google Chrome
sudo dnf install google-chrome-stable
```

## Usage

### Basic Usage

```bash
# Search for milk products
python3 iga_scraper.py milk

# Search for bread products with 2 pages
python3 iga_scraper.py bread --pages 2

# Search and sort by price (cheapest first)
python3 iga_scraper.py milk --sort price

# Search and sort by price (most expensive first)
python3 iga_scraper.py milk --sort price --reverse

# Show only discounted products
python3 iga_scraper.py milk --discounted-only

# Save results to JSON file
python3 iga_scraper.py milk --output milk_products.json
```

### Command Line Options

- `query`: Search term (required)
- `--pages`: Number of pages to scrape (default: 1)
- `--sort`: Sort by 'price' or 'discount' (default: price)
- `--reverse`: Sort in descending order
- `--discounted-only`: Show only products with discounts
- `--output`: Save results to JSON file
- `--headless`: Run browser in headless mode (default: True)

### Examples

```bash
# Find cheapest milk products across 3 pages
python3 iga_scraper.py milk --pages 3 --sort price

# Find most expensive bread products
python3 iga_scraper.py bread --sort price --reverse

# Find discounted chocolate products and save to file
python3 iga_scraper.py chocolate --discounted-only --output chocolate_deals.json

# Search for coffee with detailed output
python3 iga_scraper.py coffee --pages 2 --sort discount --output coffee_products.json
```

## Output Format

The scraper outputs product information in the following format:

```
1. Product Name
   Price: $X.XX
   Discount: N/A or discount text
   Image: https://image-url.com/image.jpg
```

When saved to JSON, the format is:

```json
[
  {
    "name": "Product Name",
    "price": "$X.XX",
    "image_url": "https://image-url.com/image.jpg",
    "discount": "N/A or discount text"
  }
]
```

## Technical Details

### Architecture

The scraper uses:
- **Selenium WebDriver**: For dynamic content loading and JavaScript execution
- **BeautifulSoup**: For HTML parsing and data extraction
- **Chrome/Chromium**: As the browser engine

### How It Works

1. **Navigation**: Uses Selenium to navigate to IGA search pages
2. **Content Loading**: Waits for dynamic content to load completely
3. **HTML Parsing**: Extracts the page source and parses with BeautifulSoup
4. **Data Extraction**: Identifies product containers and extracts relevant information
5. **Processing**: Cleans and formats the extracted data
6. **Sorting/Filtering**: Applies user-specified sorting and filtering options

### Selectors Used

The scraper identifies products using these CSS selectors:
- Product containers: `div.product-card_wrapper` or `div[role="listitem"]`
- Product names: `a.product-card-name`
- Prices: `span.price`
- Images: `img` tags within product containers
- Discounts: `span.discount-text`

## Limitations

- **Rate Limiting**: The scraper includes delays to avoid overwhelming the server
- **Dynamic Content**: Some content may require additional loading time
- **Structure Changes**: Website structure changes may require selector updates
- **Geographic Restrictions**: May only work for Australian IGA stores

## Error Handling

The scraper includes error handling for:
- Network connectivity issues
- Missing elements
- Invalid search queries
- Browser initialization problems

## Legal Considerations

This scraper is intended for educational and personal use only. Please ensure you comply with:
- IGA's Terms of Service
- Robots.txt guidelines
- Local data protection laws
- Respectful scraping practices (reasonable delays, limited requests)

## Troubleshooting

### Common Issues

1. **No products found**: 
   - Check if the search term is valid
   - Verify internet connection
   - Try a different search query

2. **Browser errors**:
   - Ensure Chrome/Chromium is installed
   - ChromeDriver is automatically managed by webdriver-manager
   - Check system compatibility

3. **Slow performance**:
   - Reduce the number of pages
   - Increase wait times in the code
   - Check internet connection speed

### Debug Mode

To run in non-headless mode for debugging:

```bash
python3 iga_scraper.py milk --headless False
```

## Contributing

To improve the scraper:
1. Test with different product categories
2. Update selectors if website structure changes
3. Add error handling for edge cases
4. Optimize performance and reliability

## Version History

- **v1.0**: Initial release with basic scraping functionality
- **v1.1**: Added sorting and filtering options
- **v1.2**: Improved error handling and JSON export
- **v1.3**: Enhanced product detection and data extraction
- **v1.4**: Implemented webdriver-manager for automatic ChromeDriver management

## Support

For issues or questions:
1. Check the troubleshooting section
2. Verify your Python and dependency versions
3. Test with simple queries first
4. Review the error messages for specific issues

---

**Note**: This tool is for educational purposes. Always respect website terms of service and implement appropriate delays to avoid overloading servers.

