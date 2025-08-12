import json
import os
import time
import sys
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Global cache for Coles products to avoid reloading the file
_coles_products_cache = None
_cache_timestamp = None
_cache_file_path = None

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


def load_coles_products():
    """
    Load Coles products from file with caching to avoid repeated file reads
    
    Returns:
        list: List of all Coles products
    """
    global _coles_products_cache, _cache_timestamp, _cache_file_path
    
    # Path to the merged products file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    merged_file_path = os.path.join(current_dir, '..', '..', '..', 'generated', 'coles_merged_products.json')
    
    # Check if we need to reload the cache
    need_reload = (
        _coles_products_cache is None or 
        _cache_file_path != merged_file_path or
        (os.path.exists(merged_file_path) and 
         os.path.getmtime(merged_file_path) > _cache_timestamp)
    )
    
    if need_reload:
        log_and_print(f"Loading Coles products file from: {merged_file_path}")
        
        try:
            # Check if file exists
            if not os.path.exists(merged_file_path):
                log_and_print(f"Coles products file not found at {merged_file_path}", 'error')
                return []
            
            # Read and parse the JSON file
            with open(merged_file_path, 'r', encoding='utf-8') as file:
                _coles_products_cache = json.load(file)
            
            _cache_timestamp = time.time()
            _cache_file_path = merged_file_path
            log_and_print(f"Loaded and cached {len(_coles_products_cache)} total Coles products")
            
        except FileNotFoundError:
            log_and_print(f"Error: The file {merged_file_path} was not found.", 'error')
            return []
        except json.JSONDecodeError as e:
            log_and_print(f"Error parsing JSON file: {e}", 'error')
            return []
        except Exception as e:
            log_and_print(f"Error reading or processing Coles products file: {e}", 'error')
            return []
    else:
        log_and_print(f"Using cached Coles products ({len(_coles_products_cache)} items)")
    
    return _coles_products_cache or []


def fetch_coles_products_from_file(query, limit=50):
    """
    Fetch products from Coles merged products JSON file
    
    Args:
        query (str): Search term to filter products
        limit (int): Maximum number of products to return
    
    Returns:
        list: List of product dictionaries matching the query
    """
    # Load products (with caching)
    all_products = load_coles_products()
    
    if not all_products:
        return []
    
    log_and_print(f"Searching for query: '{query.lower()}'")
    
    # Filter products based on query
    filtered_products = []
    query_lower = query.lower()
    
    for product in all_products:
        title = product.get('title', '').lower()
        if query_lower in title:
            # Convert to standardized format
            standardized_product = {
                'name': product.get('title', ''),
                'price': f"${product.get('current_price', 0):.2f}" if product.get('current_price') else 'N/A',
                'price_numeric': product.get('current_price', 0),
                'original_price': f"${product.get('original_price', 0):.2f}" if product.get('original_price') else None,
                'discount_price': f"${product.get('current_price', 0):.2f}" if product.get('current_price') else 'N/A',
                'discount_percentage': product.get('discount_percentage'),
                'discount_amount': product.get('discount_amount'),
                'imageUrl': product.get('image_url', ''),
                'productUrl': product.get('product_url', ''),
                'brand': product.get('brand', 'Coles'),
                'category': product.get('category', ''),
                'weight_size': product.get('weight_size', ''),
                'per_unit_price': product.get('per_unit_price', ''),
                'store': 'Coles'
            }
            filtered_products.append(standardized_product)
            
            # Stop if we've reached the limit
            if len(filtered_products) >= limit:
                break
    
    log_and_print(f"Found {len(filtered_products)} products matching query")
    return filtered_products


def fetch_coles_special_products(limit=500):
    """
    Fetch special/discounted products from Coles merged products file
    
    Args:
        limit (int): Maximum number of special products to return
    
    Returns:
        list: List of special product dictionaries
    """
    # Load products (with caching)
    all_products = load_coles_products()
    
    if not all_products:
        return []
    
    log_and_print(f"Searching for special products in {len(all_products)} total Coles products")
    
    # Filter for special/discounted products
    special_products = []
    
    for product in all_products:
        # Check if product has discount or is in specials category
        has_discount = (
            product.get('discount_percentage') is not None or
            product.get('discount_amount') is not None or
            product.get('original_price') is not None or
            product.get('category') == 'specials' or
            'was' in product.get('per_unit_price', '').lower()
        )
        
        if has_discount:
            # Convert to standardized format
            standardized_product = {
                'name': product.get('title', ''),
                'price': f"${product.get('current_price', 0):.2f}" if product.get('current_price') else 'N/A',
                'price_numeric': product.get('current_price', 0),
                'original_price': f"${product.get('original_price', 0):.2f}" if product.get('original_price') else None,
                'original_price_numeric': product.get('original_price'),
                'discount_price': f"${product.get('current_price', 0):.2f}" if product.get('current_price') else 'N/A',
                'discount_percentage': product.get('discount_percentage'),
                'discount_amount': product.get('discount_amount'),
                'imageUrl': product.get('image_url', ''),
                'productUrl': product.get('product_url', ''),
                'brand': product.get('brand', 'Coles'),
                'category': product.get('category', ''),
                'weight_size': product.get('weight_size', ''),
                'per_unit_price': product.get('per_unit_price', ''),
                'store': 'Coles',
                'product_type': 'special'
            }
            
            # Calculate savings if possible
            if product.get('original_price') and product.get('current_price'):
                original = product['original_price']
                current = product['current_price']
                if original > current:
                    standardized_product['savings_amount'] = original - current
                    standardized_product['savings_percentage'] = round(((original - current) / original) * 100, 1)
            
            special_products.append(standardized_product)
            
            # Stop if we've reached the limit
            if len(special_products) >= limit:
                break
    
    log_and_print(f"Found {len(special_products)} special products")
    return special_products


def coles_parse_price(price_str):
    """Converts '$1.99' to float 1.99"""
    try:
        if isinstance(price_str, (int, float)):
            return float(price_str)
        return float(str(price_str).replace('$', '').replace(',', '')) if price_str else float('inf')
    except (ValueError, TypeError):
        return float('inf')


def parse_price(price_str):
    """Converts '$1.99' to float 1.99 (alias for backwards compatibility)"""
    return coles_parse_price(price_str)


def scrape_coles(query, limit=50):
    """Main method to scrape Coles for products"""
    log_and_print(f"Searching Coles for: '{query}'")
    results = fetch_coles_products_from_file(query, limit)
    log_and_print(f"Fetched {len(results)} products for query: '{query}'")
    
    if results:
        try:
            sorted_products = sorted(results, key=lambda x: coles_parse_price(x.get('price', '999')))
        except Exception as e:
            log_and_print(f"Error sorting products: {e}", 'warning')
            sorted_products = results
        return sorted_products
    else:
        log_and_print("No products found.")
        return []


# Usage example
if __name__ == '__main__':
    # Check if special mode is requested
    time_start = time.time()
    
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['--special', 'special']:
        # Special products mode
        target_count = 500
        if len(sys.argv) > 2:
            try:
                target_count = int(sys.argv[2])
            except ValueError:
                print("Invalid target count, using default 500")
        
        print(f"Fetching {target_count} Coles special products...")
        special_products = fetch_coles_special_products(target_count)
        
        log_and_print(f"\nFetched {len(special_products)} special products total")
        
        if special_products:
            sorted_products = sorted(special_products, key=lambda x: parse_price(x.get('price', '999')))
            
            for i, product in enumerate(sorted_products, 1):
                print("--->>>")
                print(f"Special Product {i}:")
                print(f"Name: {product['name']}")
                print(f"Price: {product['price']}")
                if product.get('original_price'):
                    print(f"Original Price: {product['original_price']}")
                if product.get('savings_amount'):
                    print(f"Savings: ${product['savings_amount']:.2f}")
                if product.get('discount_percentage'):
                    print(f"Discount: {product['discount_percentage']}%")
                print(f"Per Unit Price: {product.get('per_unit_price', 'N/A')}")
                print(f"Image URL: {product['imageUrl']}")
                print(f"Category: {product['category']}")
                print("---")
        else:
            print("No special products found.")
            
    elif len(sys.argv) > 1:
        # Regular search mode
        query = sys.argv[1]
        log_and_print(f"Searching for: '{query}'")
        results = fetch_coles_products_from_file(query)
        log_and_print(f"Fetched {len(results)} products for query: '{query}'")
        
        if results:
            sorted_products = sorted(results, key=lambda x: parse_price(x.get('price', '999')))

            for i, product in enumerate(sorted_products, 1):
                print("--->>>")
                print(f"Product {i}:")
                print(f"Name: {product['name']}")
                print(f"Price: {product['price']}")
                if product.get('original_price'):
                    print(f"Original Price: {product['original_price']}")
                print(f"Per Unit Price: {product.get('per_unit_price', 'N/A')}")
                print(f"Image URL: {product['imageUrl']}")
                print(f"Brand: {product.get('brand', 'N/A')}")
                print(f"Category: {product['category']}")
                print("---")
        else:
            print("No products found.")
    else:
        print("Usage:")
        print("  python coles_scrapper.py <search_query>  - Search for specific products")
        print("  python coles_scrapper.py --special       - Fetch all special products")
        print("\nExample:")
        print("  python coles_scrapper.py milk")
        print("  python coles_scrapper.py --special")
    
    time_end = time.time()
    log_and_print(f"Time taken: {time_end - time_start:.2f} seconds")
