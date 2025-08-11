import requests
import time
import sys
import logging

# Configure logging
logger = logging.getLogger(__name__)

def log_and_print(message, level='info'):
    """Log message once using the configured logger"""
    if level.lower() == 'info':
        logger.info(message)
    elif level.lower() == 'error':
        logger.error(message)
    elif level.lower() == 'warning':
        logger.warning(message)
    elif level.lower() == 'debug':
        logger.debug(message)


def fetch_aldi_products_with_discount(query, limit=24, service_point='G452'):
    # Store the original requested limit (total products desired)
    max_products_wanted = limit
    
    # ALDI API only accepts specific limit values as page size
    valid_page_sizes = [12, 16, 24, 30, 32, 48, 60]
    page_size = min(valid_page_sizes, key=lambda x: abs(x - limit))
    log_and_print(f"ALDI: Requested {max_products_wanted} products; using page size {page_size} (ALDI API requirement)")
    
    base_url = "https://api.aldi.com.au/v3/product-search"
    offset = 0
    products = []
    
    # Start timing for 5-second timeout
    start_time = time.time()
    timeout_seconds = 5

    while len(products) < max_products_wanted:
        # Check if we've exceeded the timeout
        if time.time() - start_time > timeout_seconds:
            log_and_print(f"ALDI search for '{query}' timed out after {timeout_seconds}s, returning {len(products)} products")
            break
        # Calculate how many more products we need
        remaining_needed = max_products_wanted - len(products)
        
        # Use the standard page size, but we'll break early if we get enough
        params = {
            'currency': 'AUD',
            'serviceType': 'walk-in',
            'q': query,
            'limit': page_size,
            'offset': offset,
            'sort': 'relevance',
            'testVariant': 'A',
            'servicePoint': service_point
        }

        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            log_and_print(f"Failed to fetch data: HTTP {response.status_code}")
            break

        data = response.json()

        log_and_print(f"line 57: Data length: {len(data)}")
        if 'data' not in data or len(data['data']) == 0:
            break

        # Process items from this page, but stop if we reach our limit
        for item in data['data']:
            if len(products) >= max_products_wanted:
                break
                
            product = {}
            product['name'] = item.get('name')
            product['categoryKey'] = None  # No category info in search results
            product['categoryName'] = None  # No category info in search results
            
            price_obj = item.get('price', {})
            product['price'] = price_obj.get('amountRelevantDisplay')
            # Discount price if available (usually None unless discounted)
            product['discount_price'] = price_obj.get('wasPriceDisplay')
            
            # Image (choose 'FR01' type if available, else default to first)
            image_url = None
            assets = item.get('assets', [])
            for asset in assets:
                if asset.get('assetType') == 'FR01':
                    image_url = asset.get('url')
                    break
            if not image_url and assets:
                image_url = assets[0].get('url')
            # Fill width/slug placeholders for image URL
            if image_url:
                slug = item.get('urlSlugText', '')
                image_url = image_url.replace('{width}', '300').replace('{slug}', slug)
            product['imageUrl'] = image_url
            products.append(product)

        # Check if we have enough products or if there are no more pages
        if len(products) >= max_products_wanted:
            log_and_print(f"Reached desired limit of {max_products_wanted} products")
            break
            
        pagination = data.get('meta', {}).get('pagination', {})
        total = pagination.get('totalCount', 0)
        offset += page_size
        if offset >= total:
            log_and_print(f"Reached end of results (total available: {total})")
            break
            
        # Respectful delay to avoid hammering the API
        time.sleep(1)

    log_and_print(f"{time.time()} ALDI scraper returning {len(products)} products (requested: {max_products_wanted})")
    return products

# Assuming products is a list of dicts with a 'price' key as string like '$1.99'
# limit is [12,16,24,30,32,48,60] 
def fetch_aldi_special_products(service_point='G452', limit=16):
    """
    Fetch special products from all categories available at Aldi
    
    Args:
        service_point (str): Service point identifier (default: 'G452')
        limit (int): Number of products to fetch per category (default: 30)
    
    Returns:
        list: List of products with same structure as fetch_aldi_products_with_discount
    """
    # First, get all categories
    categories_url = "https://api.aldi.com.au/v2/product-category-tree"
    categories_params = {
        # 'serviceType': 'walk-in',
        # 'servicePoint': service_point
    }
    
    print("Fetching categories...")
    categories_response = requests.get(categories_url, params=categories_params)
    if categories_response.status_code != 200:
        log_and_print(f"Failed to fetch categories: HTTP {categories_response.status_code}")
        return {}
    
    categories_data = categories_response.json()
    all_products = []
    
    # Extract categories - assuming the API returns a nested structure
    def extract_categories(data):
        category_keys = []
        for category in data:
            category_key = category.get('key')
            category_name = category.get('name')
            
            if category_key:
                category_keys.append((category_key, category_name))
            
            log_and_print(f"Category: {category_name}")
            
            # Check for subcategories
            # subcategories = category.get('children', [])
            # if subcategories:
                # category_keys.extend(extract_categories(subcategories))
        
        return category_keys
    
    # Get all category keys
    if 'data' in categories_data:
        categories_list = extract_categories(categories_data['data'])
    else:
        categories_list = extract_categories(categories_data)
    
    log_and_print(f"Found {len(categories_list)} categories")

    categories_list = [name for name in categories_list if name[1] not in ['Liquor', 'Cleaning & Household', 'Baby', 'Drinks', 'Cleaning & Household', 'Pets', ]]

    log_and_print(f"Found {len(categories_list)} categories after filtering")
    
    # For each category, fetch products
    for category_key, category_name in categories_list:
        log_and_print(f"Fetching products for category: {category_name}")
        
        products_url = "https://api.aldi.com.au/v3/product-search"
        products_params = {
            'currency': 'AUD',
            'serviceType': 'walk-in',
            'categoryKey': category_key,
            'limit': limit,
            'offset': 0,
            'sort': 'price',
            'testVariant': 'A',
            'servicePoint': service_point
        }
        
        products_response = requests.get(products_url, params=products_params)
        if products_response.status_code != 200:
            log_and_print(f"Failed to fetch products for category {category_name}: HTTP {products_response.status_code}")
            continue
        
        products_data = products_response.json()
        category_products = []
        
        if 'data' in products_data and products_data['data']:
            for item in products_data['data']:
                product = {}
                product['name'] = item.get('name')
                product['categoryKey'] = category_key
                product['categoryName'] = category_name
                
                price_obj = item.get('price', {})
                product['price'] = price_obj.get('amountRelevantDisplay')
                product['discount_price'] = price_obj.get('wasPriceDisplay')
                
                # Image handling
                image_url = None
                assets = item.get('assets', [])
                for asset in assets:
                    if asset.get('assetType') == 'FR01':
                        image_url = asset.get('url')
                        break
                if not image_url and assets:
                    image_url = assets[0].get('url')
                
                if image_url:
                    slug = item.get('urlSlugText', '')
                    image_url = image_url.replace('{width}', '300').replace('{slug}', slug)
                
                product['imageUrl'] = image_url
                all_products.append(product)
        
        if 'data' in products_data and products_data['data']:
            log_and_print(f"  Found {len(products_data['data'])} products")
        else:
            log_and_print(f"  No products found")
        
        # Respectful delay between API calls
        time.sleep(0.5)
    
    return all_products

def aldi_parse_price(price_str):
    # Converts '$1.99' to float 1.99
    return float(price_str.replace('$', '')) if price_str else float('inf')

def parse_price(price_str):
    # Converts '$1.99' to float 1.99 (alias for backwards compatibility)
    return aldi_parse_price(price_str)

def scrape_aldi(query, limit=24):
    """Main method to scrape ALDI for products"""
    log_and_print(f"Searching ALDI for: '{query}'")
    results = fetch_aldi_products_with_discount(query, limit)
    log_and_print(f"Fetched {len(results)} products for query: '{query}'")
    
    if results:
        sorted_products = sorted(results, key=lambda x: aldi_parse_price(x['price']))
        return sorted_products
    else:
        print("No products found.")
        return []

# Usage example
if __name__ == '__main__':
    # Check if special mode is requested
    time_start = time.time()
    if len(sys.argv) > 1 and sys.argv[1] == '--special':
        print("Fetching special products from all categories...")
        special_products = fetch_aldi_special_products()
        
        log_and_print(f"\nFetched {len(special_products)} products total")
        sorted_products = sorted(special_products, key=lambda x: parse_price(x['price']))
        
        for i, product in enumerate(sorted_products, 1):
            print("--->>>")
            log_and_print(f"Product {i}:")
            log_and_print(f"Name: {product['name']}")
            log_and_print(f"Price: {product['price']}")
            log_and_print(f"Discount Price: {product['discount_price'] if product['discount_price'] else 'No discount'}")
            log_and_print(f"Image URL: {product['imageUrl']}")
            log_and_print(f"Category: {product['categoryName']}")
            print("---")
        
    elif len(sys.argv) > 1:
        query = sys.argv[1]
        log_and_print(f"Searching for: '{query}'")
        results = fetch_aldi_products_with_discount(query)
        log_and_print(f"Fetched {len(results)} products for query: '{query}'")
        sorted_products = sorted(results, key=lambda x: parse_price(x['price']))

        for i, product in enumerate(sorted_products, 1):
            print("--->>>")
            log_and_print(f"Product {i}:")
            log_and_print(f"Name: {product['name']}")
            log_and_print(f"Price: {product['price']}")
            log_and_print(f"Discount Price: {product['discount_price'] if product['discount_price'] else 'No discount'}")
            log_and_print(f"Image URL: {product['imageUrl']}")
            print("---")
    
    else:
        print("Usage:")
        print("  python aldi_scrapper.py <search_query>  - Search for specific products")
        print("  python aldi_scrapper.py --special       - Fetch all special products by category")
        print("\nExample:")
        print("  python aldi_scrapper.py milk")
        print("  python aldi_scrapper.py --special")
    time_end = time.time()
    log_and_print(f"Time taken: {time_end - time_start} seconds")