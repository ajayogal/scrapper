import requests
import time
from typing import List, Dict, Tuple


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
    Attempt to fetch products from Harris Farm search page using HTTP requests and HTML parsing.

    Note: Harris Farm may use Cloudflare or client-side rendering which can block plain HTTP scrapers.
    This function mirrors the JS scraper's intent as closely as possible without a headless browser.
    """
    from bs4 import BeautifulSoup  # requires beautifulsoup4

    base_url = "https://www.harrisfarm.com.au"
    search_url = (
        f"{base_url}/search?q={requests.utils.quote(query)}"
        "&type=product%2Carticle%2Ccollection&options%5Bprefix%5D=last"
    )

    session = _build_session()

    try:
        resp = session.get(search_url, timeout=30)
        if resp.status_code != 200:
            print(f"Failed to load page: HTTP {resp.status_code}")
            return []

        # Simple Cloudflare/challenge detection
        text_preview = resp.text[:1000].lower()
        if ("just a moment" in text_preview) or ("connection needs to be verified" in text_preview):
            print("Detected Cloudflare challenge page; unable to proceed without a headless browser.")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        products: List[Dict] = []
        seen: set[str] = set()

        # Try multiple container selectors similar to the JS implementation
        product_selectors = [
            ".product-card",
            ".product-item",
            "[class*='product-card']",
            "[class*='ProductCard']",
            "[class*='product']",
        ]

        product_elements = []
        for css in product_selectors:
            found = soup.select(css)
            if found:
                product_elements = found
                break

        # Fallback to product links if no obvious cards
        if not product_elements:
            product_elements = soup.select("a[href*='/product']")

        def extract_from_container(container) -> Tuple[Dict, str]:
            # Name
            name = ""
            for sel in [
                "h3",
                "h2",
                "[class*='title']",
                "[class*='name']",
                ".product-title",
                "a[href*='/product']",
            ]:
                el = container.select_one(sel)
                if el:
                    name = _extract_text(el)
                    if name and len(name) > 3:
                        break

            if name:
                import re as _re
                name = _re.sub(r"\s+", " ", name).strip()
                name = _re.sub(r"\$[\d,.]+.*$", "", name).strip()
                if len(name) > 80:
                    words = name.split(" ")
                    name = " ".join(words[:6])

            # Prices
            price_text = ""
            unit_price_text = ""
            discount_amount = ""

            for price_el in container.select("[class*='price']"):
                full_text = _extract_text(price_el)
                parsed = parse_complex_price(full_text)
                if parsed.get("mainPrice"):
                    price_text = parsed["mainPrice"]
                    unit_price_text = parsed.get("unitPrice", "")
                    discount_amount = parsed.get("discount", "")
                    break
                # simple fallback
                import re as _re2
                if _re2.search(r"\$\d+\.?\d*", full_text):
                    price_text = full_text
                    break

            # Try to find unit price separately if not within price block
            if not unit_price_text:
                for unit_el in container.select("[class*='unit'], [class*='per'], [class*='kg'], [class*='each']"):
                    unit_text = _extract_text(unit_el)
                    import re as _re3
                    m = _re3.search(r"\$?(\d+\.?\d*)\s*(?:/\s*)?(kg|g|each|ea|per|l|ml)", unit_text, _re3.I)
                    if m:
                        unit_price_text = f"${m.group(1)} / {m.group(2)}"
                        break

            unit_price_numeric = ""
            if unit_price_text:
                import re as _re4
                m = _re4.search(r"\$?(\d+\.?\d*)", unit_price_text)
                if m:
                    unit_price_numeric = m.group(1)

            # Image and URL
            image_el = container.select_one("img")
            image_url = ""
            if image_el:
                if image_el.has_attr("src") and image_el.get("src"):
                    image_url = image_el.get("src")
                elif image_el.has_attr("data-src") and image_el.get("data-src"):
                    image_url = image_el.get("data-src")
                elif image_el.has_attr("data-original") and image_el.get("data-original"):
                    image_url = image_el.get("data-original")
                elif image_el.has_attr("srcset") and image_el.get("srcset"):
                    srcset_val = image_el.get("srcset")
                    try:
                        image_url = srcset_val.split(",")[0].strip().split(" ")[0]
                    except Exception:
                        image_url = srcset_val

            link_el = container.select_one("a")
            product_url = link_el.get("href") if link_el and link_el.has_attr("href") else (
                container.get("href") if container.name == "a" and container.has_attr("href") else ""
            )

            # Discount/original logic
            discount = discount_amount or ""
            discounted_price = ""
            original_price = price_text
            if discount_amount and price_text:
                parsed_again = parse_complex_price(price_text)
                if parsed_again.get("originalPrice"):
                    original_price = parsed_again["originalPrice"]
                    discounted_price = price_text
            else:
                disc_el = container.select_one("[class*='discount'], [class*='save'], [class*='was']")
                if disc_el:
                    discount = _extract_text(disc_el)
                    was_el = container.select_one("[class*='was'], [class*='original']")
                    was_text = _extract_text(was_el)
                    if was_text:
                        original_price = was_text
                        discounted_price = price_text

            # Stock status
            in_stock = True
            stock_el = container.select_one("[class*='out-of-stock'], [class*='unavailable']")
            if stock_el or (container.get_text(" ", strip=True).lower().find("out of stock") != -1):
                in_stock = False

            # Brand
            brand = ""
            brand_el = container.select_one("[class*='brand']")
            if brand_el:
                brand = _extract_text(brand_el)
            elif name:
                brand = name.split(" ")[0]

            # Category (not always available on search page)
            category = ""
            cat_el = container.select_one("[class*='category'], [class*='breadcrumb']")
            if cat_el:
                category = _extract_text(cat_el)

            # Numeric price for sorting
            try:
                numeric_price = float((price_text or "0").replace("$", "").replace(",", ""))
            except ValueError:
                numeric_price = 0.0

            image_url_full = _normalize_url("https://www.harrisfarm.com.au", image_url)
            product_url_full = _normalize_url("https://www.harrisfarm.com.au", product_url)

            product: Dict = {
                "store": "Harris Farm Markets",
                "title": name,
                "price": original_price,
                "discount": discount,
                "discountedPrice": discounted_price,
                "numericPrice": numeric_price,
                "inStock": in_stock,
                "unitPrice": unit_price_numeric or "",
                "unitPriceText": unit_price_text or "",
                "imageUrl": image_url_full,
                "productUrl": product_url_full,
                "brand": brand,
                "category": category,
                "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            # Make a stable uniqueness key (use normalized title + numeric price)
            key = f"{(name or '').lower().strip()}-{numeric_price:.2f}"
            return product, key

        for idx, container in enumerate(product_elements):
            if len(products) >= max_results:
                break
            product, key = extract_from_container(container)
            if not product.get("title") or not product.get("price"):
                continue
            if key in seen:
                continue
            seen.add(key)
            products.append(product)

        return products[:max_results]

    except Exception as exc:
        print(f"Error scraping Harris Farm Markets: {exc}")
        return []


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


