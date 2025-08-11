import requests
import time
from typing import List, Dict, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException


def parse_complex_price(price_string: str) -> Dict[str, str]:
    """
    Parse complex price strings like "Save $2.00 $8.99 ea $17.98 / kg" into components.

    Returns a dict with keys: mainPrice, unitPrice, discount, originalPrice
    """
    result = {
        "mainPrice": "",
        "unitPrice": "",
        "discount": "",
        "originalPrice": "",
    }

    if not price_string:
        return result

    clean_price = " ".join(price_string.split()).strip()

    # Extract discount information (Save $X.XX or $X.XX off, etc.)
    import re

    discount_match = re.search(r"(?:save|off|discount)\s*\$?(\d+\.?\d*)", clean_price, re.I)
    if discount_match:
        result["discount"] = f"${discount_match.group(1)}"

    # Extract all price tokens
    price_matches = re.findall(r"\$\d+\.?\d*", clean_price) or []
    if len(price_matches) == 0:
        return result

    # Strategy 1: Discount present → first $ is discount, second $ is main
    if result["discount"] and len(price_matches) >= 2:
        result["mainPrice"] = price_matches[1]
        after_main = clean_price[clean_price.find(result["mainPrice"]) + len(result["mainPrice"]) :]
        unit_match = re.search(r"\$(\d+\.?\d*)\s*\/?\s*(kg|g|each|ea|per|l|ml)", after_main, re.I)
        if unit_match:
            result["unitPrice"] = f"${unit_match.group(1)} / {unit_match.group(2)}"

        try:
            discount_num = float(result["discount"].replace("$", ""))
            current_num = float(result["mainPrice"].replace("$", ""))
            result["originalPrice"] = f"${current_num + discount_num:.2f}"
        except ValueError:
            pass

    # Strategy 2: Look for "ea" or "each"
    elif " ea" in clean_price.lower() or " each" in clean_price.lower():
        each_match = re.search(r"\$(\d+\.?\d*)\s*(?:ea|each)", clean_price, re.I)
        if each_match:
            result["mainPrice"] = f"${each_match.group(1)}"
            unit_match = re.search(r"\$(\d+\.?\d*)\s*\/?\s*(kg|g|per|l|ml)", clean_price, re.I)
            if unit_match and unit_match.group(0) != result["mainPrice"]:
                result["unitPrice"] = f"${unit_match.group(1)} / {unit_match.group(2)}"

    # Strategy 3: Default – first price is main, then try to find unit price
    else:
        result["mainPrice"] = price_matches[0]
        unit_match = re.search(r"\$(\d+\.?\d*)\s*\/?\s*(kg|g|each|ea|per|l|ml)", clean_price, re.I)
        if unit_match and unit_match.group(0) != result["mainPrice"]:
            result["unitPrice"] = f"${unit_match.group(1)} / {unit_match.group(2)}"

    return result


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
    )
    return session


def _normalize_url(base: str, url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    if not url.startswith("/"):
        # Assume relative path
        return f"{base.rstrip('/')}/{url}"
    return f"{base.rstrip('/')}{url}"


def _extract_text(element) -> str:
    return element.get_text(strip=True) if element else ""


def fetch_harris_products(query: str, max_results: int = 50) -> List[Dict]:
    """
    Fetch products from Harris Farm search page using Selenium for JavaScript rendering.
    """
    from bs4 import BeautifulSoup
    
    base_url = "https://www.harrisfarm.com.au"
    search_url = (
        f"{base_url}/search?q={requests.utils.quote(query)}"
        "&type=product%2Carticle%2Ccollection&options%5Bprefix%5D=last"
    )

    driver = None
    try:
        print(f"Loading Harris Farm search page: {search_url}")
        
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Create driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        # Navigate to page
        driver.get(search_url)
        
        # Wait for page to load and check for Cloudflare
        time.sleep(3)
        
        # Check if we're on a Cloudflare challenge page
        title = driver.title
        if "Just a moment" in title or "connection needs to be verified" in driver.page_source:
            print("Detected Cloudflare challenge, waiting...")
            # Wait longer for Cloudflare to complete
            time.sleep(10)
            
            # Check if challenge is resolved
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: "Just a moment" not in d.title and "connection needs to be verified" not in d.page_source
                )
                print("Cloudflare challenge completed")
            except TimeoutException:
                print("Cloudflare challenge may still be active, continuing anyway...")
        
        # Wait for products to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".product-card, [class*='product']"))
            )
        except TimeoutException:
            print("Products not found within timeout, continuing with current page content...")
        
        # Get page content after JavaScript execution
        soup = BeautifulSoup(driver.page_source, "html.parser")
        print(f"Parsed HTML - title: {soup.title.string if soup.title else 'No title'}")

        products: List[Dict] = []
        seen: set[str] = set()

        # Try multiple container selectors
        product_selectors = [
            ".product-card",
            ".product-item", 
            "[class*='product-card']",
            "[class*='ProductCard']",
            "[class*='product']"
        ]

        product_elements = []
        for css in product_selectors:
            found = soup.select(css)
            print(f"Selector '{css}' found {len(found)} elements")
            if found:
                product_elements = found
                print(f"Using selector: {css}")
                break

        # Fallback to product links
        if not product_elements:
            product_elements = soup.select("a[href*='/product']")
            print(f"Fallback: Found {len(product_elements)} product links")
            
        print(f"Total product elements to process: {len(product_elements)}")

        for idx, container in enumerate(product_elements):
            if len(products) >= max_results:
                break
                
            # Extract product name
            name = ""
            name_selectors = ['h3', 'h2', '[class*="title"]', '[class*="name"]', '.product-title', 'a[href*="/product"]']
            for sel in name_selectors:
                el = container.select_one(sel)
                if el:
                    name = _extract_text(el)
                    if name and len(name) > 3:
                        break

            if name:
                import re
                name = re.sub(r"\s+", " ", name).strip()
                name = re.sub(r"\$[\d,.]+.*$", "", name).strip()
                if len(name) > 80:
                    words = name.split(" ")
                    name = " ".join(words[:6])

            # Extract price - look for multiple price patterns
            price_text = ""
            unit_price_text = ""
            discount_amount = ""

            # Try various price selectors
            price_selectors = [
                "[class*='price']",
                ".price",
                "[data-price]",
                ".cost",
                ".amount"
            ]
            
            for price_sel in price_selectors:
                price_elements = container.select(price_sel)
                for price_el in price_elements:
                    full_text = _extract_text(price_el)
                    if full_text and "$" in full_text:
                        # Parse complex price
                        parsed = parse_complex_price(full_text)
                        if parsed.get("mainPrice"):
                            price_text = parsed["mainPrice"]
                            unit_price_text = parsed.get("unitPrice", "")
                            discount_amount = parsed.get("discount", "")
                            break
                        # Simple fallback
                        import re
                        if re.search(r"\$\d+\.?\d*", full_text):
                            price_text = full_text
                            break
                if price_text:
                    break

            # Debug for first few products
            if idx < 3:
                print(f"Product {idx + 1}: name='{name}', price='{price_text}'")

            # Extract other details
            image_url = ""
            image_el = container.select_one("img")
            if image_el:
                image_url = (image_el.get("src") or 
                           image_el.get("data-src") or 
                           image_el.get("data-original") or "")

            link_el = container.select_one("a")
            product_url = ""
            if link_el:
                product_url = link_el.get("href", "")
            elif container.name == "a":
                product_url = container.get("href", "")

            # Normalize URLs
            image_url_full = _normalize_url(base_url, image_url)
            product_url_full = _normalize_url(base_url, product_url)

            # Extract brand
            brand = ""
            brand_el = container.select_one("[class*='brand']")
            if brand_el:
                brand = _extract_text(brand_el)
            elif name:
                brand = name.split(" ")[0]

            # Check stock
            in_stock = True
            if container.select_one("[class*='out-of-stock'], [class*='unavailable']"):
                in_stock = False
            elif "out of stock" in container.get_text(" ", strip=True).lower():
                in_stock = False

            # Parse numeric price
            try:
                numeric_price = float((price_text or "0").replace("$", "").replace(",", ""))
            except ValueError:
                numeric_price = 0.0

            if name and price_text:
                # Create unique identifier
                product_id = f"{name.lower().strip()}-{numeric_price:.2f}"
                
                if product_id not in seen:
                    seen.add(product_id)
                    
                    product = {
                        "store": "Harris Farm Markets",
                        "title": name,
                        "price": price_text,
                        "discount": discount_amount,
                        "discountedPrice": "",
                        "numericPrice": numeric_price,
                        "inStock": in_stock,
                        "unitPrice": "",
                        "unitPriceText": unit_price_text,
                        "imageUrl": image_url_full,
                        "productUrl": product_url_full,
                        "brand": brand,
                        "category": "",
                        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                    
                    products.append(product)

        return products[:max_results]

    except Exception as exc:
        print(f"Error scraping Harris Farm Markets: {exc}")
        return []
    finally:
        if driver:
            driver.quit()


def get_harris_product_details(product_url: str) -> Dict:
    """Fetch simple product details from a product page."""
    from bs4 import BeautifulSoup  # requires beautifulsoup4

    session = _build_session()
    try:
        resp = session.get(product_url, timeout=30)
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        details = {
            "description": _extract_text(soup.select_one(".product-description, .description")),
            "ingredients": _extract_text(soup.select_one(".ingredients")),
            "nutritionalInfo": _extract_text(soup.select_one(".nutritional-info, .nutrition")),
            "brand": _extract_text(soup.select_one(".brand")),
            "size": _extract_text(soup.select_one(".size, .pack-size")),
            "origin": _extract_text(soup.select_one(".origin, .country-of-origin")),
        }
        return details
    except Exception:
        return {}


def parse_price_numeric(price_str: str) -> float:
    try:
        return float((price_str or "").replace("$", "").replace(",", ""))
    except Exception:
        return float("inf")


def scrape_harris(query: str, max_results: int = 50) -> List[Dict]:
    """Convenience wrapper mirroring other scrapers' API."""
    print(f"Searching Harris Farm Markets for: '{query}'")
    results = fetch_harris_products(query, max_results)
    print(f"Fetched {len(results)} products for query: '{query}'")
    if results:
        try:
            results = sorted(results, key=lambda x: parse_price_numeric(str(x.get("price", "999"))))
        except Exception:
            pass
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = input("Enter search query: ").strip()

    items = scrape_harris(query, max_results=24)
    for i, product in enumerate(items, 1):
        print("--->>>")
        print(f"Product {i}:")
        print(f"Name: {product.get('title')}")
        print(f"Price: {product.get('price')}")
        if product.get("discount"):
            print(f"Discount: {product.get('discount')}")
        if product.get("discountedPrice"):
            print(f"Discounted Price: {product.get('discountedPrice')}")
        print(f"Unit Price: {product.get('unitPriceText')}")
        print(f"Image URL: {product.get('imageUrl')}")
        print(f"Product URL: {product.get('productUrl')}")
        print(f"Brand: {product.get('brand')}")
        print(f"Store: {product.get('store')}")
        print("---")


