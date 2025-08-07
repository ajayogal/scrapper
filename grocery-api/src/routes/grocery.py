from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import subprocess
import json
import os
import hashlib
import time
import sys
import logging
import random

# Import the Python scrapers from local scrapers module
try:
    from src.scrapers import (
        fetch_aldi_products_with_discount, 
        aldi_parse_price,
        fetch_iga_products, 
        iga_parse_price
    )
    PYTHON_SCRAPERS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import Python scrapers: {e}")
    print("Falling back to Node.js scrapers")
    PYTHON_SCRAPERS_AVAILABLE = False

grocery_bp = Blueprint('grocery', __name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log_and_print(message, level='info'):
    """Print message to console and log it with proper flushing"""
    print(message)
    sys.stdout.flush()  # Force flush the output buffer
    
    if level.lower() == 'info':
        logger.info(message)
    elif level.lower() == 'error':
        logger.error(message)
    elif level.lower() == 'warning':
        logger.warning(message)
    elif level.lower() == 'debug':
        logger.debug(message)

# In-memory cache for search results
search_cache = {}
CACHE_DURATION = 300  # 5 minutes in seconds

def get_cache_key(query, store):
    """Generate a cache key for the search parameters"""
    return hashlib.md5(f"{query.lower()}:{store}".encode()).hexdigest()

def is_cache_valid(cache_entry):
    """Check if cache entry is still valid"""
    return time.time() - cache_entry['timestamp'] < CACHE_DURATION

def run_python_scrapers(query, store='all', max_results=200):
    """Run the Python scrapers for ALDI and IGA"""
    try:
        all_products = []
        
        if store == 'all' or store == 'aldi-py':
            try:
                log_and_print(f"LN-64: Scraping ALDI for: {query}")
                aldi_products = fetch_aldi_products_with_discount(query, limit=min(max_results, 100))
                
                # Convert ALDI products to standard format
                for product in aldi_products:
                    log_and_print(f"LN-69: Product: {product}")
                    standardized_product = {
                        'title': product.get('name', ''),
                        'store': 'Aldi',
                        'price': product.get('price', ''),
                        'discountedPrice': product.get('discount_price', ''),
                        'discount': f"Was {product.get('discount_price')}" if product.get('discount_price') else '',
                        'numericPrice': aldi_parse_price(product.get('price', '0')),
                        'inStock': True,  # Assume in stock if returned by API
                        'unitPrice': '',  # Not available in ALDI scraper
                        'imageUrl': product.get('image', ''),
                        'brand': '',  # Extract from name if needed
                        'category': '',  # Not available in ALDI scraper
                        'productUrl': '',  # Not available in ALDI scraper
                        'scraped_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')
                    }
                    all_products.append(standardized_product)
                    
            except Exception as e:
                log_and_print(f"Error scraping ALDI: {e}", 'error')
        
        if store == 'all' or store == 'iga-py':
            try:
                log_and_print(f"LN-91: Scraping IGA for: {query}")
                iga_products = fetch_iga_products(query, limit=min(max_results, 100))
                
                # Convert IGA products to standard format
                for product in iga_products:
                    standardized_product = {
                        'title': product.get('name', ''),
                        'store': 'IGA',
                        'price': str(product.get('price', '')),
                        'discountedPrice': str(product.get('discount_price', '')) if product.get('discount_price') else '',
                        'discount': f"Was {product.get('discount_price')}" if product.get('discount_price') else '',
                        'numericPrice': iga_parse_price(str(product.get('price', '0'))),
                        'inStock': True,  # Assume in stock if returned by API
                        'unitPrice': '',  # Not available in IGA scraper
                        'imageUrl': product.get('image', ''),
                        'brand': '',  # Extract from name if needed
                        'category': '',  # Not available in IGA scraper
                        'productUrl': '',  # Not available in IGA scraper
                        'scraped_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')
                    }
                    all_products.append(standardized_product)
                    
            except Exception as e:
                log_and_print(f"Error scraping IGA: {e}", 'error')
        
        return {'products': all_products}
        
    except Exception as e:
        return {"error": f"Failed to run Python scrapers: {str(e)}"}

def run_node_scraper(query, store='all', max_results=200):
    """Run the Node.js scraper using subprocess"""
    try:
        log_and_print(f"LN-124: Running Node.js scraper for: {query}")
        # Get the path to the grocery_scraper directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        grocery_scraper_path = os.path.join(current_dir, '..', '..', 'grocery_scraper')
        
        # Prepare the command to run the Node.js scraper
        cmd = ['node', 'index.js', 'search', query]
        
        if store != 'all':
            cmd.extend([store, str(max_results)])
        else:
            cmd.append(str(max_results))
            
        # Add JSON flag for API usage
        cmd.append('--json')
        
        # Run the Node.js script
        result = subprocess.run(
            cmd,
            cwd=grocery_scraper_path,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        if result.returncode == 0:
            # Parse the JSON output from the Node.js script
            try:
                output_lines = result.stdout.strip().split('\n')
                # Find the last line that looks like JSON (in case there are other log messages)
                json_output = None
                for line in reversed(output_lines):
                    try:
                        json_output = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
                
                if json_output:
                    return json_output
                else:
                    return {"error": "No valid JSON output from scraper", "stdout": result.stdout, "stderr": result.stderr}
            except json.JSONDecodeError as e:
                return {"error": f"Failed to parse JSON output: {e}", "stdout": result.stdout, "stderr": result.stderr}
        else:
            return {"error": f"Scraper failed with return code {result.returncode}", "stdout": result.stdout, "stderr": result.stderr}
    
    except subprocess.TimeoutExpired:
        return {"error": "Scraper timed out after 60 seconds"}
    except Exception as e:
        return {"error": f"Failed to run scraper: {str(e)}"}

@grocery_bp.route('/search', methods=['POST'])
@cross_origin()
def search_products():
    """Search for products across all stores or a specific store using Node.js scraper with caching"""
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        query = data['query'].strip()
        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400
        
        store = data.get('store', 'all')
        page = data.get('page', 1)
        per_page = data.get('perPage', 10)
        
        # Generate cache key
        cache_key = get_cache_key(query, store)
        
        # Check if we have cached results that are still valid
        if cache_key in search_cache and is_cache_valid(search_cache[cache_key]):
            log_and_print(f"LN-199: Using cached results for query: {query}, store: {store}")
            all_products = search_cache[cache_key]['products']
        else:
            log_and_print(f"LN-201: Fetching fresh results for query: {query}, store: {store}")
            # # Fetch more results initially to reduce the need for re-scraping
            # # Set a higher limit to get comprehensive results
            # if PYTHON_SCRAPERS_AVAILABLE and store in ['all', 'aldi-py', 'iga-py']:
            #     log_and_print("Using Python scrapers")
            #     scraper_result = run_python_scrapers(query, store, max_results=200)
            # else:
            #     log_and_print("Using Node.js scraper")
            #     scraper_result = run_node_scraper(query, store, max_results=200)
            
            scraper_result = run_node_scraper(query, store, max_results=50)

            if 'error' in scraper_result:
                return jsonify({
                    'error': 'Failed to scrape products',
                    'details': scraper_result['error'],
                    'debug': scraper_result
                }), 500
            
            # Extract products from scraper result
            if 'products' in scraper_result:
                raw_products = scraper_result['products']
            elif isinstance(scraper_result, list):
                raw_products = scraper_result
            else:
                raw_products = []

            all_products = []
            for p in raw_products:
                # Map existing fields and add missing ones
                product = {
                    "title": p.get("title", "N/A"),
                    "store": store,  # Add the store from the request
                    "price": f"${p['original_price']:.2f}" if p.get("original_price") is not None else f"${p.get('current_price', 0):.2f}",
                    "discountedPrice": f"${p['current_price']:.2f}" if p.get("discount_amount") is not None or p.get("discount_percentage") is not None else "",
                    "discount": "",
                    "numericPrice": p.get("current_price", 0),
                    "inStock": True,  # Assuming products returned are in stock
                    "unitPrice": p.get("per_unit_price", ""),
                    "imageUrl": p.get("image_url", ""),
                    "brand": p.get("brand", ""),
                    "category": p.get("category", ""),
                    "productUrl": p.get("product_url", ""),
                    "scraped_at": p.get("scraped_at", "")
                }

                # Calculate discount string
                if p.get("discount_amount") is not None:
                    product["discount"] = f"Save ${p['discount_amount']:.2f}"
                elif p.get("discount_percentage") is not None:
                    product["discount"] = f"{p['discount_percentage']}% Off"
                elif p.get("original_price") is not None and p.get("current_price") is not None and p["original_price"] > p["current_price"]:
                    savings = p["original_price"] - p["current_price"]
                    product["discount"] = f"Save ${savings:.2f}"

                all_products.append(product)
            
            # Sort by price (cheapest first)
            all_products.sort(key=lambda x: x.get('numericPrice', float('inf')))
            
            # Cache the results
            search_cache[cache_key] = {
                'products': all_products,
                'timestamp': time.time()
            }
        
        # Apply pagination to cached results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_products = all_products[start_idx:end_idx]
        
        has_more = end_idx < len(all_products)
        
        return jsonify({
            'success': True,
            'query': query,
            'store': store,
            'page': page,
            'perPage': per_page,
            'totalResults': len(all_products),
            'currentPageResults': len(paginated_products),
            'hasMore': has_more,
            'products': paginated_products,
            'cached': cache_key in search_cache and is_cache_valid(search_cache[cache_key])
        })
    
    except Exception as e:
        log_and_print(f"API error: {e}", 'error')
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@grocery_bp.route('/stores', methods=['GET'])
@cross_origin()
def get_stores():
    """Get list of supported stores"""
    stores = [
        {'id': 'all', 'name': 'All Stores'},
        {'id': 'woolworths', 'name': 'Woolworths'},
        {'id': 'coles', 'name': 'Coles'},
        {'id': 'harris', 'name': 'Harris Farm Markets'},
        {'id': 'iga', 'name': 'IGA'},
        {'id': 'aldi', 'name': 'Aldi'},
        {'id': 'iga-py', 'name': 'IGA (Python)'},
        {'id': 'aldi-py', 'name': 'Aldi (Python)'},
    ]
    
    return jsonify({
        'success': True,
        'stores': stores
    })

@grocery_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'python_scrapers_available': PYTHON_SCRAPERS_AVAILABLE,
        'node_scraper_available': True,  # Node.js scraper is available via subprocess
        'cache_entries': len(search_cache),
        'cache_keys': list(search_cache.keys())
    })

@grocery_bp.route('/cache/clear', methods=['POST'])
@cross_origin()
def clear_cache():
    """Clear the search cache"""
    global search_cache
    cache_count = len(search_cache)
    search_cache.clear()
    return jsonify({
        'success': True,
        'message': f'Cleared {cache_count} cache entries',
        'cache_entries': len(search_cache)
    })

def search_all_stores(search_keys, max_results_per_store=50, selected_stores=None):
    """Search selected stores (or all available stores) for the given search keys"""
    if selected_stores is None or len(selected_stores) == 0:
        # Default to all stores if none specified
        search_stores = ['all']
        use_python_scrapers = True
        use_node_scrapers = True
    else:
        # Use only selected stores
        search_stores = selected_stores
        
        # Determine which scrapers to use based on selected stores
        python_store_ids = ['aldi-py', 'iga-py']
        node_store_ids = ['woolworths', 'coles', 'harris', 'iga', 'aldi']
        
        use_python_scrapers = any(store in python_store_ids for store in selected_stores)
        use_node_scrapers = any(store in node_store_ids for store in selected_stores)
        
        # If 'all' is in selected stores, enable both scrapers
        if 'all' in selected_stores:
            use_python_scrapers = True
            use_node_scrapers = True
    
    all_products = []
    
    for search_key in search_keys:
        log_and_print(f"Searching stores {search_stores} for: {search_key}")
        
        # Use Python scrapers (ALDI and IGA) if needed
        if use_python_scrapers and PYTHON_SCRAPERS_AVAILABLE:
            if 'all' in search_stores:
                python_result = run_python_scrapers(search_key, 'all', max_results_per_store)
            else:
                # Filter selected python stores
                python_stores = [store for store in selected_stores if store in ['aldi-py', 'iga-py']]
                if python_stores:
                    # Convert store names for python scraper
                    python_store_map = {'aldi-py': 'aldi', 'iga-py': 'iga'}
                    mapped_stores = [python_store_map.get(store, store) for store in python_stores]
                    python_result = run_python_scrapers(search_key, mapped_stores, max_results_per_store)
                else:
                    python_result = {}
            
            if 'products' in python_result:
                all_products.extend(python_result['products'])
        
        # Use Node.js scrapers (Woolworths, Coles, Harris Farm, etc.) if needed
        if use_node_scrapers:
            if 'all' in search_stores:
                node_result = run_node_scraper(search_key, 'all', max_results_per_store)
            else:
                # Filter selected node stores
                node_stores = [store for store in selected_stores if store in ['woolworths', 'coles', 'harris', 'iga', 'aldi']]
                if node_stores:
                    # For multiple stores, we'll need to call each individually and combine
                    node_result = {'products': []}
                    for store in node_stores:
                        store_result = run_node_scraper(search_key, store, max_results_per_store)
                        if 'products' in store_result:
                            node_result['products'].extend(store_result['products'])
                        elif isinstance(store_result, list):
                            node_result['products'].extend(store_result)
                else:
                    node_result = {}
            
            if 'products' in node_result:
                all_products.extend(node_result['products'])
            elif isinstance(node_result, list):
                all_products.extend(node_result)
    
    # Remove duplicates based on title and store
    seen = set()
    unique_products = []
    for product in all_products:
        key = f"{product.get('title', '').lower()}_{product.get('store', '').lower()}"
        if key not in seen:
            seen.add(key)
            unique_products.append(product)
    
    # Sort by price (cheapest first)
    unique_products.sort(key=lambda x: x.get('numericPrice', float('inf')))
    
    return unique_products

def get_random_product_image(items):
    """Get a random product image from the list of items"""
    if not items:
        return None
    
    # Filter items that have valid image URLs
    items_with_images = [item for item in items if item.get('imageUrl')]
    
    if not items_with_images:
        return None
    
    # Return a random image URL
    random_item = random.choice(items_with_images)
    return random_item.get('imageUrl')

def calculate_total_savings(items):
    """Calculate total savings from discounted products in the list"""
    total_savings = 0.0
    discounted_items = 0
    
    for item in items:
        # Check if item has discount information
        current_price = item.get('numericPrice', 0)
        
        # Try different ways to get original price
        original_price = None
        if item.get('discountedPrice'):
            # If discountedPrice exists, current price should be the original
            try:
                original_price = float(str(item.get('price', '0')).replace('$', '').replace(',', ''))
                discounted_price = float(str(item.get('discountedPrice', '0')).replace('$', '').replace(',', ''))
                if original_price > discounted_price:
                    total_savings += (original_price - discounted_price)
                    discounted_items += 1
            except (ValueError, TypeError):
                pass
        elif item.get('discount'):
            # If discount field exists, try to calculate savings
            try:
                discount_price = float(str(item.get('discount', '0')).replace('$', '').replace(',', ''))
                if discount_price > current_price:
                    total_savings += (discount_price - current_price)
                    discounted_items += 1
            except (ValueError, TypeError):
                pass
    
    return {
        'total_savings': round(total_savings, 2),
        'discounted_items_count': discounted_items
    }

def sort_products_by_discount_priority(products):
    """Sort products to prioritize discounted items first"""
    discounted_products = []
    regular_products = []
    
    for product in products:
        # Check if product has any discount indicators
        has_discount = (
            product.get('discountedPrice') or 
            product.get('discount') or
            (product.get('price') and product.get('discountedPrice') and 
             product.get('price') != product.get('discountedPrice'))
        )
        
        if has_discount:
            discounted_products.append(product)
        else:
            regular_products.append(product)
    
    # Sort discounted products by price, then regular products by price
    discounted_products.sort(key=lambda x: x.get('numericPrice', float('inf')))
    regular_products.sort(key=lambda x: x.get('numericPrice', float('inf')))
    
    # Return discounted products first, then regular products
    return discounted_products + regular_products

def generate_shopping_lists(products, budget, num_lists=4, existing_used_products=None, used_list_names=None):
    """Generate 4 different shopping lists within the budget constraint with no duplicate products"""
    lists = []
    global_used_products = existing_used_products if existing_used_products else set()  # Track products used across all lists
    used_names = used_list_names if used_list_names else set()  # Track used list names
    
    # Create a single shuffled list and divide it into segments for each strategy
    shuffled_products = products.copy()
    random.shuffle(shuffled_products)
    
    # Generate 4 lists with random names and different strategies
    strategies = [
        ('cheapest_first', 'Maximum quantity - focuses on the cheapest items'),
        ('store_variety', 'Store variety - tries to include items from different stores'),
        ('best_value', 'Best value - prioritizes discounted items and good unit prices'),
        ('balanced', 'Balanced approach - mix of affordable and quality items')
    ]
    
    generation_functions = [
        generate_cheapest_list_unique,
        generate_variety_list_unique,
        generate_value_list_unique,
        generate_balanced_list_unique
    ]
    
    for i, ((strategy, description), generation_func) in enumerate(zip(strategies, generation_functions)):
        # Generate the list using the appropriate strategy
        generated_list = generation_func(shuffled_products, budget, global_used_products)
        
        # Get random name and image
        random_name = get_random_list_name(used_names)
        used_names.add(random_name)
        list_image = get_random_product_image(generated_list['items'])
        savings_info = calculate_total_savings(generated_list['items'])
        
        lists.append({
            'name': random_name,
            'strategy': strategy,
            'description': description,
            'items': generated_list['items'],
            'total_cost': generated_list['total_cost'],
            'items_count': len(generated_list['items']),
            'remaining_budget': budget - generated_list['total_cost'],
            'list_image': list_image,
            'total_savings': savings_info['total_savings'],
            'discounted_items_count': savings_info['discounted_items_count']
        })
    
    return lists, global_used_products, used_names

def load_list_names():
    """Load random list names from configuration file"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'list_names.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get('list_names', [])
    except Exception as e:
        log_and_print(f"Error loading list names config: {e}", 'error')
        # Fallback to default names
        return [
            "Smart Shopper", "Budget Buddy", "Value Hunter", "Thrifty Finds",
            "Deal Detective", "Savings Safari", "Penny Pincher", "Bargain Beast"
        ]

def get_random_list_name(used_names=None):
    """Get a random list name, avoiding already used names if possible"""
    available_names = load_list_names()
    
    if used_names:
        # Filter out already used names
        unused_names = [name for name in available_names if name not in used_names]
        if unused_names:
            available_names = unused_names
    
    return random.choice(available_names) if available_names else "Shopping List"

def get_product_id(product):
    """Generate a unique identifier for a product"""
    return f"{product.get('title', '')}-{product.get('store', '')}-{product.get('numericPrice', 0)}"

def generate_cheapest_list_unique(products, budget, used_products):
    """Generate a list focusing on the cheapest items, avoiding already used products"""
    items = []
    total_cost = 0.0
    
    # Sort products to prioritize discounted items first
    sorted_products = sort_products_by_discount_priority(products)
    
    for product in sorted_products:
        product_id = get_product_id(product)
        price = product.get('numericPrice', float('inf'))
        
        if (price != float('inf') and 
            total_cost + price <= budget and 
            product_id not in used_products):
            items.append(product)
            total_cost += price
            used_products.add(product_id)
    
    return {'items': items, 'total_cost': total_cost}

def generate_variety_list_unique(products, budget, used_products):
    """Generate a list with variety across different stores, avoiding already used products"""
    items = []
    total_cost = 0.0
    stores_used = set()
    
    # Sort products to prioritize discounted items first
    sorted_products = sort_products_by_discount_priority(products)
    
    # First pass: one item per store, prioritizing discounted items
    for product in sorted_products:
        product_id = get_product_id(product)
        price = product.get('numericPrice', float('inf'))
        store = product.get('store', '').lower()
        
        if (price != float('inf') and 
            total_cost + price <= budget and 
            store not in stores_used and
            product_id not in used_products):
            items.append(product)
            total_cost += price
            stores_used.add(store)
            used_products.add(product_id)
    
    # Second pass: fill remaining budget with different items, still prioritizing discounted
    for product in sorted_products:
        product_id = get_product_id(product)
        price = product.get('numericPrice', float('inf'))
        
        if (price != float('inf') and 
            total_cost + price <= budget and 
            product_id not in used_products):
            items.append(product)
            total_cost += price
            used_products.add(product_id)
    
    return {'items': items, 'total_cost': total_cost}

def generate_value_list_unique(products, budget, used_products):
    """Generate a list prioritizing discounted items and good value, avoiding already used products"""
    items = []
    total_cost = 0.0
    
    # Sort products to prioritize discounted items first
    sorted_products = sort_products_by_discount_priority(products)
    
    for product in sorted_products:
        product_id = get_product_id(product)
        price = product.get('numericPrice', float('inf'))
        
        if (price != float('inf') and 
            total_cost + price <= budget and 
            product_id not in used_products):
            items.append(product)
            total_cost += price
            used_products.add(product_id)
    
    return {'items': items, 'total_cost': total_cost}

def generate_balanced_list_unique(products, budget, used_products):
    """Generate a balanced list mixing affordable and mid-range items, avoiding already used products"""
    items = []
    total_cost = 0.0
    
    # Sort products to prioritize discounted items first
    sorted_products = sort_products_by_discount_priority(products)
    
    # Filter out already used products
    available_products = [p for p in sorted_products if get_product_id(p) not in used_products]
    
    # Categorize products by price range
    valid_products = [p for p in available_products if p.get('numericPrice', float('inf')) != float('inf')]
    if not valid_products:
        return {'items': items, 'total_cost': total_cost}
    
    prices = [p['numericPrice'] for p in valid_products]
    avg_price = sum(prices) / len(prices)
    
    cheap_products = [p for p in valid_products if p['numericPrice'] <= avg_price * 0.7]
    mid_products = [p for p in valid_products if avg_price * 0.7 < p['numericPrice'] <= avg_price * 1.3]
    
    # Alternate between cheap and mid-range items (both lists are already sorted with discounted items first)
    cheap_idx = 0
    mid_idx = 0
    use_cheap = True
    
    while total_cost < budget:
        if use_cheap and cheap_idx < len(cheap_products):
            product = cheap_products[cheap_idx]
            cheap_idx += 1
        elif mid_idx < len(mid_products):
            product = mid_products[mid_idx]
            mid_idx += 1
        elif cheap_idx < len(cheap_products):
            product = cheap_products[cheap_idx]
            cheap_idx += 1
        else:
            break
        
        product_id = get_product_id(product)
        price = product.get('numericPrice', float('inf'))
        
        if (total_cost + price <= budget and 
            product_id not in used_products):
            items.append(product)
            total_cost += price
            used_products.add(product_id)
        
        use_cheap = not use_cheap
    
    return {'items': items, 'total_cost': total_cost}

def generate_cheapest_list(products, budget):
    """Generate a list focusing on the cheapest items, prioritizing discounted products"""
    items = []
    total_cost = 0.0
    
    # Sort products to prioritize discounted items first
    sorted_products = sort_products_by_discount_priority(products)
    
    for product in sorted_products:
        price = product.get('numericPrice', float('inf'))
        if price != float('inf') and total_cost + price <= budget:
            items.append(product)
            total_cost += price
    
    return {'items': items, 'total_cost': total_cost}

def generate_variety_list(products, budget):
    """Generate a list with variety across different stores, prioritizing discounted products"""
    items = []
    total_cost = 0.0
    stores_used = set()
    used_products = set()
    
    # Sort products to prioritize discounted items first
    sorted_products = sort_products_by_discount_priority(products)
    
    # First pass: one item per store, prioritizing discounted items
    for product in sorted_products:
        price = product.get('numericPrice', float('inf'))
        store = product.get('store', '').lower()
        product_id = product.get('title', '') + product.get('store', '')
        
        if (price != float('inf') and 
            total_cost + price <= budget and 
            store not in stores_used and
            product_id not in used_products):
            items.append(product)
            total_cost += price
            stores_used.add(store)
            used_products.add(product_id)
    
    # Second pass: fill remaining budget with different items, still prioritizing discounted
    remaining_products = [p for p in sorted_products if (p.get('title', '') + p.get('store', '')) not in used_products]
    for product in remaining_products:
        price = product.get('numericPrice', float('inf'))
        product_id = product.get('title', '') + product.get('store', '')
        
        if (price != float('inf') and 
            total_cost + price <= budget and 
            product_id not in used_products):
            items.append(product)
            total_cost += price
            used_products.add(product_id)
    
    return {'items': items, 'total_cost': total_cost}

def generate_value_list(products, budget):
    """Generate a list prioritizing discounted items and good value"""
    items = []
    total_cost = 0.0
    
    # Sort products to prioritize discounted items first (this already does what we want)
    sorted_products = sort_products_by_discount_priority(products)
    
    for product in sorted_products:
        price = product.get('numericPrice', float('inf'))
        if price != float('inf') and total_cost + price <= budget:
            items.append(product)
            total_cost += price
    
    return {'items': items, 'total_cost': total_cost}

def generate_balanced_list(products, budget):
    """Generate a balanced list mixing affordable and mid-range items, prioritizing discounted products"""
    items = []
    total_cost = 0.0
    
    # Sort products to prioritize discounted items first
    sorted_products = sort_products_by_discount_priority(products)
    
    # Categorize products by price range
    valid_products = [p for p in sorted_products if p.get('numericPrice', float('inf')) != float('inf')]
    if not valid_products:
        return {'items': items, 'total_cost': total_cost}
    
    prices = [p['numericPrice'] for p in valid_products]
    avg_price = sum(prices) / len(prices)
    
    cheap_products = [p for p in valid_products if p['numericPrice'] <= avg_price * 0.7]
    mid_products = [p for p in valid_products if avg_price * 0.7 < p['numericPrice'] <= avg_price * 1.3]
    
    # Alternate between cheap and mid-range items (both lists are already sorted with discounted items first)
    cheap_idx = 0
    mid_idx = 0
    use_cheap = True
    
    while total_cost < budget:
        if use_cheap and cheap_idx < len(cheap_products):
            product = cheap_products[cheap_idx]
            cheap_idx += 1
        elif mid_idx < len(mid_products):
            product = mid_products[mid_idx]
            mid_idx += 1
        elif cheap_idx < len(cheap_products):
            product = cheap_products[cheap_idx]
            cheap_idx += 1
        else:
            break
        
        price = product.get('numericPrice', float('inf'))
        if total_cost + price <= budget:
            items.append(product)
            total_cost += price
        
        use_cheap = not use_cheap
    
    return {'items': items, 'total_cost': total_cost}

@grocery_bp.route('/auto-generated-list', methods=['POST'])
@cross_origin()
def auto_generated_list():
    """Generate 4 optimized shopping lists within budget based on search keys"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        search_keys = data.get('search_keys', [])
        budget = data.get('budget')
        
        if not search_keys:
            return jsonify({'error': 'search_keys parameter is required and must be a non-empty array'}), 400
        
        if not isinstance(search_keys, list):
            return jsonify({'error': 'search_keys must be an array of strings'}), 400
        
        if budget is None:
            return jsonify({'error': 'budget parameter is required'}), 400
        
        try:
            budget = float(budget)
            if budget <= 0:
                return jsonify({'error': 'budget must be a positive number'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'budget must be a valid number'}), 400
        
        # Optional parameters
        max_results_per_store = data.get('max_results_per_store', 50)
        selected_stores = data.get('selected_stores', [])  # New parameter for store selection
        
        log_and_print(f"Generating auto shopping lists for search keys: {search_keys}, budget: ${budget}, stores: {selected_stores}")
        
        # Search selected stores (or all stores if none specified) for all search keys
        all_products = search_all_stores(search_keys, max_results_per_store, selected_stores)
        
        if not all_products:
            return jsonify({
                'success': True,
                'message': 'No products found for the given search keys',
                'search_keys': search_keys,
                'budget': budget,
                'lists': []
            })
        
        # Filter products within individual budget (optional safety check)
        affordable_products = [p for p in all_products 
                             if p.get('numericPrice', float('inf')) <= budget]
        
        if not affordable_products:
            return jsonify({
        'success': True,
                'message': 'No individual products found within the specified budget',
                'search_keys': search_keys,
                'budget': budget,
                'total_products_found': len(all_products),
                'cheapest_product_price': min([p.get('numericPrice', float('inf')) for p in all_products]),
                'lists': []
            })
        
        # Generate 4 different shopping lists
        shopping_lists, used_products, used_names = generate_shopping_lists(affordable_products, budget)
        
        # Add metadata to response
        response = {
            'success': True,
            'search_keys': search_keys,
            'budget': budget,
            'selected_stores': selected_stores if selected_stores else ['all'],
            'total_products_found': len(all_products),
            'affordable_products_count': len(affordable_products),
            'lists_generated': len(shopping_lists),
            'lists': shopping_lists,
            'used_products': list(used_products),  # Convert set to list for JSON serialization
            'used_names': list(used_names),  # Convert set to list for JSON serialization
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        return jsonify(response)
        
    except Exception as e:
        log_and_print(f"Error in auto_generated_list: {e}", 'error')
        return jsonify({
            'error': 'Internal server error', 
            'details': str(e)
        }), 500

@grocery_bp.route('/auto-generated-list/more', methods=['POST'])
@cross_origin()
def auto_generated_list_more():
    """Generate 4 additional optimized shopping lists within budget, avoiding previously used products"""
    try:
        data = request.get_json()
        
        # Validate required parameters
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        search_keys = data.get('search_keys', [])
        budget = data.get('budget')
        used_products = data.get('used_products', [])
        used_names = data.get('used_names', [])
        
        if not search_keys:
            return jsonify({'error': 'search_keys parameter is required and must be a non-empty array'}), 400
        
        if not isinstance(search_keys, list):
            return jsonify({'error': 'search_keys must be an array of strings'}), 400
        
        if budget is None:
            return jsonify({'error': 'budget parameter is required'}), 400
        
        try:
            budget = float(budget)
            if budget <= 0:
                return jsonify({'error': 'budget must be a positive number'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'budget must be a valid number'}), 400
        
        # Optional parameters
        max_results_per_store = data.get('max_results_per_store', 50)
        selected_stores = data.get('selected_stores', [])
        
        log_and_print(f"Generating additional shopping lists for search keys: {search_keys}, budget: ${budget}, stores: {selected_stores}")
        
        # Search selected stores (or all stores if none specified) for all search keys
        all_products = search_all_stores(search_keys, max_results_per_store, selected_stores)
        
        if not all_products:
            return jsonify({
                'success': True,
                'message': 'No products found for the given search keys',
                'search_keys': search_keys,
                'lists': []
            })
        
        # Filter products within individual budget (optional safety check)
        affordable_products = [p for p in all_products 
                             if p.get('numericPrice', float('inf')) <= budget]
        
        if not affordable_products:
            return jsonify({
                'success': True,
                'message': 'No individual products found within the specified budget',
                'search_keys': search_keys,
                'budget': budget,
                'total_products_found': len(all_products),
                'cheapest_product_price': min([p.get('numericPrice', float('inf')) for p in all_products]),
                'lists': []
            })
        
        # Convert used_products and used_names lists back to sets for processing
        existing_used_products = set(used_products) if used_products else set()
        existing_used_names = set(used_names) if used_names else set()
        
        # Generate 4 additional different shopping lists
        shopping_lists, updated_used_products, updated_used_names = generate_shopping_lists(
            affordable_products, 
            budget, 
            existing_used_products=existing_used_products,
            used_list_names=existing_used_names
        )
        
        # Add metadata to response
        response = {
            'success': True,
            'search_keys': search_keys,
            'budget': budget,
            'selected_stores': selected_stores if selected_stores else ['all'],
            'total_products_found': len(all_products),
            'affordable_products_count': len(affordable_products),
            'lists_generated': len(shopping_lists),
            'lists': shopping_lists,
            'used_products': list(updated_used_products),  # Updated list of used products
            'used_names': list(updated_used_names),  # Updated list of used names
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        return jsonify(response)
        
    except Exception as e:
        log_and_print(f"Error in auto_generated_list_more: {e}", 'error')
        return jsonify({
            'error': 'Internal server error', 
            'details': str(e)
        }), 500

