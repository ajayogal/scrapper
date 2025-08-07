import requests
import time
import sys

def fetch_iga_products(query, limit=100, store_id='32600'):
    """
    Attempt to fetch products from IGA Shop Online API
    
    Note: The IGA API appears to require authentication or special headers
    that are not publicly documented. This function demonstrates the API
    structure but may not return actual product data.
    
    Args:
        query (str): Search term
        limit (int): Number of products per request
        store_id (str): IGA store ID (default: 32600)
    
    Returns:
        list: List of product dictionaries (may be empty due to API restrictions)
    """
    base_url = f"https://www.igashop.com.au/api/storefront/stores/{store_id}/search"
    
    # Common headers that might be required
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin'
    }
    
    offset = 0
    products = []

    try:
        params = {
            'q': query,
            'sort': 'price',
            'take': limit
        }

        response = requests.get(base_url, params=params, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch data: HTTP {response.status_code}")
            return products

        print(base_url)

        data = response.json()
        total_available = data.get('total', 0)
        items_returned = data.get('count', 0)
        
        print(f"API found {total_available} products but returned {items_returned} items")
        print(f"Available facets: {list(data.get('facets', {}).keys())}")
        
        # Check if there are items in the response
        if 'items' in data and len(data['items']) > 0:
            items = data['items']
            print(f"Processing {len(items)} items...")
            
            for item in items:
                product = {}
                product['name'] = item.get('name', item.get('title', 'Unknown'))
                
                # Handle price - IGA might have different price structure
                price_info = item.get('price', {})
                if isinstance(price_info, dict):
                    product['price'] = price_info.get('current', price_info.get('amount', 'N/A'))
                    product['discount_price'] = price_info.get('was', price_info.get('originalAmount'))
                else:
                    product['price'] = price_info
                    product['discount_price'] = None
                
                # Handle image URL - IGA has nested image object with multiple sizes
                image_url = None
                if 'image' in item:
                    if isinstance(item['image'], dict):
                        # Try different image size options in order of preference
                        image_url = (item['image'].get('default') or 
                                   item['image'].get('details') or 
                                   item['image'].get('cell') or 
                                   item['image'].get('template') or 
                                   item['image'].get('zoom') or
                                   item['image'].get('url') or 
                                   item['image'].get('src'))
                    else:
                        image_url = item['image']
                elif 'imageUrl' in item:
                    image_url = item['imageUrl']
                elif 'images' in item and len(item['images']) > 0:
                    first_image = item['images'][0]
                    if isinstance(first_image, dict):
                        image_url = (first_image.get('default') or 
                                   first_image.get('details') or 
                                   first_image.get('url') or 
                                   first_image.get('src'))
                    else:
                        image_url = first_image
                
                product['image'] = image_url
                product['brand'] = item.get('brand', 'IGA')
                product['unitPrice'] = item.get('pricePerUnit', 'N/A')
                product['store'] = 'IGA'
                products.append(product)
        else:
            print("⚠️  API Limitation: The IGA search API returns metadata but no actual product items.")
            print("   This likely requires:")
            print("   - Authentication tokens")
            print("   - Session cookies from logged-in user")
            print("   - Special API keys")
            print("   - Different endpoint structure")
            print("")
            print("💡 Alternative approaches:")
            print("   1. Use the existing browser-based IGA scraper")
            print("   2. Reverse engineer the web app's API calls")
            print("   3. Contact IGA for API access")

    except requests.RequestException as e:
        print(f"Request error: {e}")
    except Exception as e:
        print(f"Error processing response: {e}")

    return products

def fetch_iga_special_products(limit_per_page=100, target_products=500, store_id='32600'):
    """
    Fetch special/promotional products from IGA Shop Online API
    
    Since the promotions endpoint requires additional authentication,
    this function uses the regular search endpoint with queries for promotional terms
    and filters products that have discounts or special pricing.
    
    Args:
        limit_per_page (int): Number of products per API request (default: 100)
        target_products (int): Target number of products to fetch (default: 500)
        store_id (str): IGA store ID (default: 32600)
    
    Returns:
        list: List of special product dictionaries
    """
    # Use the regular search endpoint which works reliably
    base_url = f"https://www.igashop.com.au/api/storefront/stores/{store_id}/search"
    
    # Headers that work with the search endpoint
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin'
    }
    
    products = []
    special_product_count = 0
    
    # Search terms that typically yield promotional/special products
    promotional_queries = [
        "special",      # Items on special
        "half price",   # Half price items  
        "sale",         # Sale items
        "offer",        # Special offers
        "discount",     # Discounted items
        "promo",        # Promotional items
        "deal",         # Deal items
        "save",         # Save money items
        "reduced",      # Reduced price items
        "clearance"     # Clearance items
    ]
    
    print(f"Starting to fetch IGA special products using promotional search terms (target: {target_products})...")
    print(f"Will search for: {', '.join(promotional_queries)}")
    
    try:
        for query_idx, query in enumerate(promotional_queries):
            if special_product_count >= target_products:
                break
                
            print(f"\n--- Searching for '{query}' products ({query_idx + 1}/{len(promotional_queries)}) ---")
            
            # Search with current promotional term
            params = {
                'q': query,
                'take': limit_per_page
            }
            
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"Failed to fetch data for query '{query}': HTTP {response.status_code}")
                continue
            
            data = response.json()
            
            # Check if there are items in the response
            if 'items' in data and len(data['items']) > 0:
                items = data['items']
                print(f"Found {len(items)} items for query '{query}'")
                
                for item in items:
                    # Filter for products that actually have discounts/special pricing
                    has_discount = False
                    original_price = item.get('wasPriceNumeric', 0)
                    current_price = item.get('priceNumeric', 0)
                    price_label = item.get('priceLabel', '').lower()
                    
                    # Check if this is actually a special/discounted product
                    if (original_price and current_price and original_price > current_price) or \
                       any(term in price_label for term in ['special', 'half', 'price', 'off', 'save', 'deal', 'discount']):
                        has_discount = True
                    
                    # Only include products that have actual discounts or special pricing
                    if has_discount:
                        product = {}
                        product['name'] = item.get('name', 'Unknown')
                        
                        # Handle price using IGA API structure
                        product['price'] = item.get('price', 'N/A')
                        product['price_numeric'] = item.get('priceNumeric', 0)
                        product['original_price'] = item.get('wasPrice', None)
                        product['original_price_numeric'] = item.get('wasPriceNumeric', None)
                        product['discount_price'] = item.get('price', 'N/A')
                        
                        # Handle image URL - IGA API structure
                        image_url = None
                        image_data = item.get('image', {})
                        if isinstance(image_data, dict):
                            image_url = image_data.get('default')
                        else:
                            image_url = image_data
                        
                        product['image'] = image_url
                        product['brand'] = item.get('brand', 'IGA')
                        product['unitPrice'] = item.get('pricePerUnit', 'N/A')
                        product['store'] = 'IGA'
                        product['product_type'] = 'special'  # Mark as special product
                        product['promotion_id'] = item.get('productId', item.get('sku', 'N/A'))
                        product['sku'] = item.get('sku', 'N/A')
                        
                        # Additional special product fields from IGA API
                        product['promotion_text'] = item.get('priceLabel', '')
                        product['description'] = item.get('description', '')
                        product['sellBy'] = item.get('sellBy', '')
                        product['unitOfSize'] = item.get('unitOfSize', {})
                        product['available'] = item.get('available', True)
                        product['search_query'] = query  # Track which query found this product
                        
                        # Calculate savings if possible
                        if original_price and current_price and original_price > current_price:
                            product['savings_amount'] = original_price - current_price
                            product['savings_percentage'] = round(((original_price - current_price) / original_price) * 100, 1)
                        
                        # TPR (Temporary Price Reduction) information
                        tpr_info = item.get('tprPrice', [])
                        if tpr_info and len(tpr_info) > 0:
                            tpr = tpr_info[0]
                            product['markdown_amount'] = tpr.get('markdown', 0)
                            product['tpr_label'] = tpr.get('label', '')
                            product['tpr_active'] = tpr.get('active', False)
                        
                        # Promotion information
                        promotions = item.get('promotions', [])
                        product['promotions_count'] = item.get('totalNumberOfPromotions', 0)
                        if promotions:
                            product['promotion_details'] = [p.get('name', '') for p in promotions]
                        
                        products.append(product)
                        special_product_count += 1
                        
                        # Stop if we've reached the target
                        if special_product_count >= target_products:
                            break
                
                print(f"Added {len([p for p in products if p.get('search_query') == query])} special products from '{query}' search")
            else:
                print(f"No items found for query '{query}'")
                
        # Remove duplicates based on SKU
        seen_skus = set()
        unique_products = []
        for product in products:
            sku = product.get('sku', product.get('promotion_id', ''))
            if sku not in seen_skus:
                seen_skus.add(sku)
                unique_products.append(product)
        
        products = unique_products[:target_products]  # Ensure we don't exceed target
        
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except Exception as e:
        print(f"Error processing response: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"Successfully fetched {len(products)} special products from IGA")
    return products

# Assuming products is a list of dicts with a 'price' key as string like '$1.99'
def parse_price(price_str):
    # Converts '$1.99' to float 1.99
    return float(price_str.replace('$', '')) if price_str else float('inf')

def use_browser_scraper_alternative(query):
    """
    Demonstrates how to use the working browser-based IGA scraper
    as an alternative to the API approach.
    """
    print("🔄 Using browser-based scraper as alternative...")
    print("   To use the working IGA scraper, run:")
    print(f"   cd ../iga && python iga_scraper.py --query '{query}' --pages 1")
    print("")
    print("   Or from JavaScript:")
    print(f"   cd ../grocery-api/grocery_scraper && node index.js search '{query}' iga 10")
    return []

# Usage example
if __name__ == '__main__':
    # Check if special products mode is requested
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'special':
        # Special products mode
        target_count = 500
        if len(sys.argv) > 2:
            try:
                target_count = int(sys.argv[2])
            except ValueError:
                print("Invalid target count, using default 500")
        
        print(f"Fetching {target_count} IGA special products...")
        results = fetch_iga_special_products(target_products=target_count)
        print(f"Fetched {len(results)} special products")
        
        if results:
            # Sort products by price if available
            try:
                sorted_products = sorted(results, key=lambda x: parse_price(str(x.get('price', '999'))))
            except:
                sorted_products = results

            for i, product in enumerate(sorted_products, 1):
                print("--->>>")
                print(f"Special Product {i}:")
                print(f"Name: {product['name']}")
                print(f"Price: {product['price']} (${product['price_numeric']:.2f})")
                print(f"Original Price: {product['original_price'] if product['original_price'] else 'N/A'}")
                if product.get('markdown_amount'):
                    print(f"Savings: ${product['markdown_amount']:.2f}")
                print(f"Promotion Text: {product['promotion_text']}")
                print(f"TPR Label: {product.get('tpr_label', 'N/A')}")
                print(f"Image URL: {product['image']}")
                print(f"Brand: {product['brand']}")
                print(f"Store: {product['store']}")
                print(f"Unit Price: {product['unitPrice']}")
                print(f"SKU: {product['sku']}")
                print(f"Available: {product['available']}")
                print(f"Promotions Count: {product['promotions_count']}")
                print("---")
        else:
            print("No special products found.")
    else:
        # Regular search mode
        # Check if query is provided as command line argument
        if len(sys.argv) > 1:
            query = sys.argv[1]
        else:
            # Fallback to user input if no command line argument
            query = input("Enter search query (or 'special' for special products): ").strip()
            if not query:
                print("No query provided. Exiting.")
                sys.exit(1)
            
            # Check if user wants special products
            if query.lower() == 'special':
                print("Fetching 500 IGA special products...")
                results = fetch_iga_special_products()
                print(f"Fetched {len(results)} special products")
                
                if results:
                    # Sort products by price if available
                    try:
                        sorted_products = sorted(results, key=lambda x: parse_price(str(x.get('price', '999'))))
                    except:
                        sorted_products = results

                    for i, product in enumerate(sorted_products, 1):
                        print("--->>>")
                        print(f"Special Product {i}:")
                        print(f"Name: {product['name']}")
                        print(f"Price: {product['price']} (${product['price_numeric']:.2f})")
                        print(f"Original Price: {product['original_price'] if product['original_price'] else 'N/A'}")
                        if product.get('markdown_amount'):
                            print(f"Savings: ${product['markdown_amount']:.2f}")
                        print(f"Promotion Text: {product['promotion_text']}")
                        print(f"TPR Label: {product.get('tpr_label', 'N/A')}")
                        print(f"Image URL: {product['image']}")
                        print(f"Brand: {product['brand']}")
                        print(f"Store: {product['store']}")
                        print(f"Unit Price: {product['unitPrice']}")
                        print(f"SKU: {product['sku']}")
                        print(f"Available: {product['available']}")
                        print(f"Promotions Count: {product['promotions_count']}")
                        print("---")
                else:
                    print("No special products found.")
                sys.exit(0)
        
        print(f"Searching IGA for: '{query}'")
        results = fetch_iga_products(query)
        print(f"Fetched {len(results)} products for query: '{query}'")
        
        if results:
            # Sort products by price if available
            try:
                sorted_products = sorted(results, key=lambda x: parse_price(str(x.get('price', '999'))))
            except:
                sorted_products = results

            for i, product in enumerate(sorted_products, 1):
                print("--->>>")
                print(f"Product {i}:")
                print(f"Name: {product['name']}")
                print(f"Price: {product['price']}")
                print(f"Discount Price: {product['discount_price'] if product['discount_price'] else 'No discount'}")
                print(f"Image URL: {product['image']}")
                print(f"Brand: {product['brand']}")
                print(f"Store: {product['store']}")
                print(f"Unit Price: {product['unitPrice']}")
                print("---")
        else:
            print("No products found using the API approach.")
            print("")
            use_browser_scraper_alternative(query)
