#!/usr/bin/env python3
"""
IGA Shop Online Scraper
A web scraper for iga.com.au to extract product details including:
- Product name
- Price
- Image URL
- Discount information
- Search functionality
- Sorting by price and discount
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import re
import json
import argparse

class IGAScraper:
    def __init__(self, headless=True):
        """Initialize the IGA scraper with Chrome WebDriver."""
        self.base_url = "https://www.igashop.com.au"
        self.driver = self._setup_driver(headless)
        
    def _setup_driver(self, headless):
        """
        Set up Chrome WebDriver with appropriate options.
        """
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        webdriver_service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)
        return driver
    
    def search_products(self, query, max_pages=1, interactive=False, specific_page=None):
        """
        Search for products on IGA website.
        
        Args:
            query (str): Search term
            max_pages (int): Maximum number of pages to scrape (0 = all available pages)
            interactive (bool): Ask user before loading each new page
            specific_page (int): Scrape only a specific page number
            
        Returns:
            list: List of product dictionaries
        """
        products = []
        
        # If specific page is requested, scrape only that page
        if specific_page:
            page = specific_page
            search_url = f"{self.base_url}/search/{page}?q={query}"
            print(f"Scraping page {page}: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(10)  # Wait for page to load
            
            # Get page source and parse with BeautifulSoup
            html_content = self.driver.page_source
            page_products = self._parse_products(html_content)
            
            if page_products:
                products.extend(page_products)
                print(f"Found {len(page_products)} products on page {page}")
            else:
                print(f"No products found on page {page}")
                
            return products
        
        # Regular multi-page scraping
        page = 1
        
        while True:
            # Check if we should stop based on max_pages limit
            if max_pages > 0 and page > max_pages:
                break
                
            search_url = f"{self.base_url}/search/{page}?q={query}"
            print(f"Scraping page {page}: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(10)  # Wait for page to load
            
            # Get page source and parse with BeautifulSoup
            html_content = self.driver.page_source
            page_products = self._parse_products(html_content)
            
            if not page_products:
                print(f"No products found on page {page}")
                break
                
            products.extend(page_products)
            print(f"Found {len(page_products)} products on page {page}")
            
            # Interactive mode: ask user if they want to continue
            if interactive and (max_pages == 0 or page < max_pages):
                print(f"\nCurrent total: {len(products)} products")
                user_input = input("Continue to next page? (y/n/show): ").lower().strip()
                
                if user_input == 'show':
                    # Show current results
                    print(f"\n=== Current Results ({len(products)} products) ===")
                    for i, product in enumerate(products, 1):
                        discount_text = f" (save {product['discount']})" if product['discount'] != "N/A" else ""
                        print(f"{i}. {product['name']} - {product['price']} ({product['quantity']}){discount_text}")
                    print("="*50)
                    
                    # Ask again
                    user_input = input("Continue to next page? (y/n): ").lower().strip()
                
                if user_input not in ['y', 'yes']:
                    print("Stopping pagination as requested.")
                    break
            
            page += 1
            
        return products
    
    def _parse_products(self, html_content):
        """
        Parse product information from HTML content.
        
        Args:
            html_content (str): HTML content of the page
            
        Returns:
            list: List of product dictionaries
        """
        soup = BeautifulSoup(html_content, "html.parser")
        products = []
        

        
        # Find all elements that are likely product cards. 
        # Based on the browser_view, each product is within a distinct block.
        # Let's look for common patterns that encapsulate a product: 
        # - a link with a product name (e.g., index 61, 65, 69, 73, 77)
        # - an image (e.g., index 60, 64, 68, 72, 76)
        # - a price (e.g., near index 61, 65, 69, 73, 77)
        
        # A good starting point is to find the product name links, then navigate up to a common parent.
        # From the screenshot, it looks like the product name link is within a div that also contains the image and price.
        # Let's try to find the product cards by looking for the image element, as it seems to be a consistent identifier.
        
        # The new website structure uses links with href="/product/..." containing product information
        product_links = soup.find_all("a", href=lambda x: x and "/product/" in x)
        

        
        for product_link in product_links:
            # Extract name from image alt text
            image_element = product_link.find("img")
            name = image_element.get("alt", "N/A") if image_element else "N/A"
            
            # Get image URL
            image_url = image_element.get("src", "N/A") if image_element else "N/A"
            
            # Find the parent container that might contain price information
            # We need to look at the parent or sibling elements for price
            parent = product_link.parent
            price = "N/A"
            quantity = "N/A"
            discount = "N/A"
            
            # Look for price in parent or nearby elements
            # We need to search more broadly - the price might be in the grandparent or next sibling
            search_containers = [parent, parent.parent if parent else None, product_link.find_next_sibling()]
            search_containers = [c for c in search_containers if c is not None]
            
            for container in search_containers:
                # Get ALL text from the container that contains dollar signs
                container_text = container.get_text() if container else ""
                
                # Check for special badge first - this is the key indicator
                special_badge = container.find(attrs={"data-badge": "special"})
                has_special = special_badge is not None
                
                # Try to find price in various common patterns
                # Prioritize special/discounted prices over regular prices
                price_selectors = [
                    "[data-badge='special'] *:contains('$')",  # Items with special badge
                    "[class*='special'] *:contains('$')",      # Special price containers
                    "[class*='discount'] *:contains('$')",     # Discount price containers
                    "[class*='sale'] *:contains('$')",         # Sale price containers
                    "[data-test-id*='special'] *:contains('$')",  # Special test IDs
                    "span[class*='price']", 
                    "div[class*='price']", 
                    "[data-test-id*='price']", 
                    "*:contains('$')"
                ]
                
                for price_selector in price_selectors:
                    try:
                        price_elements = container.select(price_selector)
                        if price_elements:
                            raw_price = price_elements[0].get_text(strip=True)
                            

                            
                            if '$' in raw_price:  # Only accept if it actually contains a dollar sign
                                # Extract quantity/size information before extracting price
                                # Pattern: "ProductName{size/quantity}{price}..."
                                # Examples: "1 Litre$2.75", "2 Litre$6.90", "300 Millilitre$3.50"
                                quantity_patterns = [
                                    r'(\d+(?:\.\d+)?\s*(?:Litre|Liter|L))',  # Litres
                                    r'(\d+(?:\.\d+)?\s*(?:Millilitre|Milliliter|mL|ML))',  # Millilitres
                                    r'(\d+(?:\.\d+)?\s*(?:Gram|g|G))',  # Grams
                                    r'(\d+(?:\.\d+)?\s*(?:Kilogram|kg|KG))',  # Kilograms
                                    r'(\d+(?:\.\d+)?\s*(?:Pack|pk))',  # Packs
                                    r'(\d+(?:\.\d+)?\s*(?:Each|ea))',  # Each
                                ]
                                
                                for pattern in quantity_patterns:
                                    quantity_match = re.search(pattern, raw_price, re.IGNORECASE)
                                    if quantity_match:
                                        quantity = quantity_match.group(1).strip()
                                        break
                                
                                # Extract all prices from the text to find the best one
                                price_matches = re.findall(r'\$\d+\.\d+', raw_price)
                                if price_matches:
                                    # If we detected a special badge, handle special pricing logic
                                    if has_special and len(price_matches) >= 2:
                                        # With special badge: usually "was $X.XX now $Y.YY"
                                        # The discounted price is typically the lower one
                                        price1 = float(price_matches[0].replace('$', ''))
                                        price2 = float(price_matches[1].replace('$', ''))
                                        
                                        if price2 < price1:
                                            # Second price is lower (discounted)
                                            price = price_matches[1]
                                            savings = price1 - price2
                                            discount = f"${savings:.2f}"
                                        else:
                                            # First price is lower (discounted)
                                            price = price_matches[0]
                                            savings = price2 - price1
                                            discount = f"${savings:.2f}"
                                    elif has_special:
                                        # Special badge but only one price - it's already the special price
                                        price = price_matches[0]
                                        discount = "Special price"
                                    elif len(price_matches) >= 2:
                                        # Multiple prices without special badge
                                        if any(word in raw_price.lower() for word in ['was', 'now', 'special', 'save']):
                                            # Take the second price as it's likely the discounted price
                                            price = price_matches[1]
                                            price1 = float(price_matches[0].replace('$', ''))
                                            price2 = float(price_matches[1].replace('$', ''))
                                            savings = price1 - price2
                                            discount = f"${savings:.2f}"
                                        else:
                                            # Take the first price
                                            price = price_matches[0]
                                    else:
                                        price = price_matches[0]
                                else:
                                    price = raw_price  # Fallback to full text
                                break
                    except:
                        continue
                if price != "N/A" and '$' in price:
                    break
                
                # Fallback: If no price found via selectors, analyze the full container text
                if price == "N/A" and '$' in container_text:
                    # Extract all prices from the full container text
                    price_matches = re.findall(r'\$\d+\.\d+', container_text)
                    if price_matches:
                        # Look for patterns that indicate special pricing
                        container_lower = container_text.lower()
                        
                        # Check for special badge or common special price patterns
                        if has_special or any(word in container_lower for word in ['special', 'was', 'now', 'save', 'off']):
                            if len(price_matches) >= 2:
                                # Usually: "was $X.XX now $Y.YY" or "$X.XX $Y.YY save"
                                # Choose the lower price as the current special price
                                price1 = float(price_matches[0].replace('$', ''))
                                price2 = float(price_matches[1].replace('$', ''))
                                
                                if price2 < price1:
                                    savings = price1 - price2
                                    discount = f"${savings:.2f}"
                                    price = price_matches[1]
                                else:
                                    savings = price2 - price1
                                    discount = f"${savings:.2f}"
                                    price = price_matches[0]
                            else:
                                price = price_matches[0]
                                discount = "Special price"
                        else:
                            # Take the first price found
                            price = price_matches[0]
                        
                        # Also extract quantity from the full text
                        if quantity == "N/A":
                            quantity_patterns = [
                                r'(\d+(?:\.\d+)?\s*(?:Litre|Liter|L))',
                                r'(\d+(?:\.\d+)?\s*(?:Millilitre|Milliliter|mL|ML))',
                                r'(\d+(?:\.\d+)?\s*(?:Gram|g|G))',
                                r'(\d+(?:\.\d+)?\s*(?:Kilogram|kg|KG))',
                                r'(\d+(?:\.\d+)?\s*(?:Pack|pk))',
                                r'(\d+(?:\.\d+)?\s*(?:Each|ea))',
                            ]
                            
                            for pattern in quantity_patterns:
                                quantity_match = re.search(pattern, container_text, re.IGNORECASE)
                                if quantity_match:
                                    quantity = quantity_match.group(1).strip()
                                    break
                        
                        break
                
                # Look for discount information
                discount_selectors = ["span[class*='discount']", "div[class*='discount']", "span[class*='special']", "[data-test-id*='discount']"]
                for discount_selector in discount_selectors:
                    discount_elements = parent.select(discount_selector)
                    if discount_elements:
                        discount = discount_elements[0].get_text(strip=True)
                        break
            
            # Clean up image URL if it's relative
            if image_url and not image_url.startswith("http"):
                if image_url.startswith("//"):
                    image_url = "https:" + image_url
                else:
                    image_url = self.base_url + image_url

            # Only add product if a name is found (to avoid non-product images)
            if name != "N/A":
                products.append({
                    "name": name,
                    "price": price,
                    "quantity": quantity,
                    "image_url": image_url,
                    "discount": discount
                })

        # Remove duplicates based on name (optional, but good for clean data)
        seen_names = set()
        unique_products = []
        for product in products:
            if product["name"] not in seen_names:
                seen_names.add(product["name"])
                unique_products.append(product)

        return unique_products
    
    def sort_products(self, products, sort_by="price", reverse=False):
        """
        Sort products by price or discount.
        
        Args:
            products (list): List of product dictionaries
            sort_by (str): "price" or "discount"
            reverse (bool): True for descending order
            
        Returns:
            list: Sorted list of products
        """
        if sort_by == "price":
            return sorted(products, key=lambda x: self._extract_price_value(x["price"]), reverse=reverse)
        elif sort_by == "discount":
            # Sort by discount availability (discounted items first)
            return sorted(products, key=lambda x: x["discount"] != "N/A", reverse=True)
        else:
            return products
    
    def _extract_price_value(self, price_str):
        """
        Extract numeric value from price string.
        
        Args:
            price_str (str): Price string like "$5.99"
            
        Returns:
            float: Numeric price value
        """
        if price_str == "N/A":
            return float("inf")
        
        # Extract numbers from price string
        numbers = re.findall(r"\d+\.?\d*", price_str)
        if numbers:
            return float(numbers[0])
        return float("inf")
    
    def get_discounted_products(self, products):
        """
        Filter products that have discounts.
        
        Args:
            products (list): List of product dictionaries
            
        Returns:
            list: List of discounted products
        """
        return [p for p in products if p["discount"] != "N/A"]
    
    def save_to_json(self, products, filename):
        """
        Save products to JSON file.
        
        Args:
            products (list): List of product dictionaries
            filename (str): Output filename
        """
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(products)} products to {filename}")
    
    def close(self):
        """
        Close the WebDriver.
        """
        if self.driver:
            self.driver.quit()

def main():
    """
    Main function to run the scraper.
    """
    parser = argparse.ArgumentParser(description="IGA Shop Online Scraper")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages to scrape (use 0 for all available pages)")
    parser.add_argument("--page", type=int, help="Scrape a specific page number (overrides --pages)")
    parser.add_argument("--sort", choices=["price", "discount"], default="price", help="Sort by price or discount")
    parser.add_argument("--reverse", action="store_true", help="Sort in descending order")
    parser.add_argument("--discounted-only", action="store_true", help="Show only discounted products")
    parser.add_argument("--output", help="Output JSON filename")
    parser.add_argument("--no-headless", action="store_true", help="Run in non-headless mode (show browser window)")
    parser.add_argument("--interactive", action="store_true", help="Ask before loading each new page")
    
    args = parser.parse_args()
    
    scraper = IGAScraper(headless=not args.no_headless)
    
    try:
        print(f"Searching for \'{args.query}\' on IGA Shop Online...")
        # Determine if we're scraping a specific page or multiple pages
        if args.page:
            products = scraper.search_products(args.query, specific_page=args.page)
        else:
            products = scraper.search_products(args.query, args.pages, args.interactive)
        
        if not products:
            print("No products found!")
            return
        
        print(f"\nFound {len(products)} total products")
        
        # Filter discounted products if requested
        if args.discounted_only:
            products = scraper.get_discounted_products(products)
            print(f"Filtered to {len(products)} discounted products")
        
        # Sort products
        products = scraper.sort_products(products, args.sort, args.reverse)
        
        # Display results
        sort_order = "descending" if args.reverse else "ascending"
        print(f"\nProducts sorted by {args.sort} ({sort_order}):")
        print("-" * 80)
        
        for i, product in enumerate(products, 1):
            print(f"{i}. {product['name']}")
            print(f"   Current Price: {product['price']}")
            print(f"   Quantity: {product['quantity']}")
            print(f"   Discount: {product['discount']}")
            print(f"   Image: {product['image_url']}")
            print()
        
        # Save to JSON if requested
        if args.output:
            scraper.save_to_json(products, args.output)
    
    finally:
        scraper.close()

if __name__ == "__main__":
    main()

