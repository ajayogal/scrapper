import requests
import time
import sys

def fetch_aldi_products_with_discount(query, limit=24, service_point='G452'):
    # ALDI API only accepts specific limit values
    valid_limits = [12, 16, 24, 30, 32, 48, 60]
    if limit not in valid_limits:
        # Find the closest valid limit
        limit = min(valid_limits, key=lambda x: abs(x - limit))
        print(f"Adjusted limit to {limit} (ALDI API requirement)")
    
    base_url = "https://api.aldi.com.au/v3/product-search"
    offset = 0
    products = []

    while True:
        params = {
            'currency': 'AUD',
            'serviceType': 'walk-in',
            'q': query,
            'limit': limit,
            'offset': offset,
            'sort': 'relevance',
            'testVariant': 'A',
            'servicePoint': service_point
        }

        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            print(f"Failed to fetch data: HTTP {response.status_code}")
            break

        data = response.json()
        if 'data' not in data or len(data['data']) == 0:
            break

        for item in data['data']:
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

        pagination = data.get('meta', {}).get('pagination', {})
        total = pagination.get('totalCount', 0)
        offset += limit
        if offset >= total:
            break
        # Respectful delay to avoid hammering the API
        time.sleep(1)

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
        print(f"Failed to fetch categories: HTTP {categories_response.status_code}")
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
            
            print(f"Category: {category_name}")
            
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
    
    print(f"Found {len(categories_list)} categories")

    categories_list = [name for name in categories_list if name[1] not in ['Liquor', 'Cleaning & Household', 'Baby', 'Drinks', 'Cleaning & Household', 'Pets', ]]

    print(f"Found {len(categories_list)} categories after filtering")
    
    # For each category, fetch products
    for category_key, category_name in categories_list:
        print(f"Fetching products for category: {category_name}")
        
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
            print(f"Failed to fetch products for category {category_name}: HTTP {products_response.status_code}")
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
            print(f"  Found {len(products_data['data'])} products")
        else:
            print(f"  No products found")
        
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
    print(f"Searching ALDI for: '{query}'")
    results = fetch_aldi_products_with_discount(query, limit)
    print(f"Fetched {len(results)} products for query: '{query}'")
    
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
        
        print(f"\nFetched {len(special_products)} products total")
        sorted_products = sorted(special_products, key=lambda x: parse_price(x['price']))
        
        for i, product in enumerate(sorted_products, 1):
            print("--->>>")
            print(f"Product {i}:")
            print(f"Name: {product['name']}")
            print(f"Price: {product['price']}")
            print(f"Discount Price: {product['discount_price'] if product['discount_price'] else 'No discount'}")
            print(f"Image URL: {product['imageUrl']}")
            print(f"Category: {product['categoryName']}")
            print("---")
        
    elif len(sys.argv) > 1:
        query = sys.argv[1]
        print(f"Searching for: '{query}'")
        results = fetch_aldi_products_with_discount(query)
        print(f"Fetched {len(results)} products for query: '{query}'")
        sorted_products = sorted(results, key=lambda x: parse_price(x['price']))

        for i, product in enumerate(sorted_products, 1):
            print("--->>>")
            print(f"Product {i}:")
            print(f"Name: {product['name']}")
            print(f"Price: {product['price']}")
            print(f"Discount Price: {product['discount_price'] if product['discount_price'] else 'No discount'}")
            print(f"Image URL: {product['imageUrl']}")
            print("---")
    
    else:
        print("Usage:")
        print("  python aldi_scrapper.py <search_query>  - Search for specific products")
        print("  python aldi_scrapper.py --special       - Fetch all special products by category")
        print("\nExample:")
        print("  python aldi_scrapper.py milk")
        print("  python aldi_scrapper.py --special")
    time_end = time.time()
    print(f"Time taken: {time_end - time_start} seconds")