from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import subprocess
import json
import os
import hashlib
import time
import sys
import logging

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
            # Fetch more results initially to reduce the need for re-scraping
            # Set a higher limit to get comprehensive results
            if PYTHON_SCRAPERS_AVAILABLE and store in ['all', 'aldi-py', 'iga-py']:
                log_and_print("Using Python scrapers")
                scraper_result = run_python_scrapers(query, store, max_results=200)
            else:
                log_and_print("Using Node.js scraper")
                scraper_result = run_node_scraper(query, store, max_results=200)
            
            # scraper_result = run_node_scraper(query, store, max_results=50)

            if 'error' in scraper_result:
                return jsonify({
                    'error': 'Failed to scrape products',
                    'details': scraper_result['error'],
                    'debug': scraper_result
                }), 500
            
            # Extract products from scraper result
            if 'products' in scraper_result:
                all_products = scraper_result['products']
            elif isinstance(scraper_result, list):
                all_products = scraper_result
            else:
                all_products = []
            
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

def search_all_stores(search_keys, max_results_per_store=50):
    """Search all available stores for the given search keys"""
    stores = ['all']  # This will use both Python and Node.js scrapers
    all_products = []
    
    for search_key in search_keys:
        log_and_print(f"Searching all stores for: {search_key}")
        
        # Use Python scrapers (ALDI and IGA)
        if PYTHON_SCRAPERS_AVAILABLE:
            python_result = run_python_scrapers(search_key, 'all', max_results_per_store)
            if 'products' in python_result:
                all_products.extend(python_result['products'])
        
        # Use Node.js scrapers (Woolworths, Coles, Harris Farm, etc.)
        node_result = run_node_scraper(search_key, 'all', max_results_per_store)
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

def generate_shopping_lists(products, budget, num_lists=4):
    """Generate 4 different shopping lists within the budget constraint"""
    lists = []
    
    # Strategy 1: Cheapest items first (maximize quantity)
    cheapest_list = generate_cheapest_list(products, budget)
    lists.append({
        'strategy': 'cheapest_first',
        'description': 'Maximum quantity - focuses on the cheapest items',
        'items': cheapest_list['items'],
        'total_cost': cheapest_list['total_cost'],
        'items_count': len(cheapest_list['items']),
        'remaining_budget': budget - cheapest_list['total_cost']
    })
    
    # Strategy 2: Balanced variety (one item per store if possible)
    variety_list = generate_variety_list(products, budget)
    lists.append({
        'strategy': 'store_variety',
        'description': 'Store variety - tries to include items from different stores',
        'items': variety_list['items'],
        'total_cost': variety_list['total_cost'],
        'items_count': len(variety_list['items']),
        'remaining_budget': budget - variety_list['total_cost']
    })
    
    # Strategy 3: Best value (considers discounts and unit prices)
    value_list = generate_value_list(products, budget)
    lists.append({
        'strategy': 'best_value',
        'description': 'Best value - prioritizes discounted items and good unit prices',
        'items': value_list['items'],
        'total_cost': value_list['total_cost'],
        'items_count': len(value_list['items']),
        'remaining_budget': budget - value_list['total_cost']
    })
    
    # Strategy 4: Balanced approach (mix of cheap and quality)
    balanced_list = generate_balanced_list(products, budget)
    lists.append({
        'strategy': 'balanced',
        'description': 'Balanced approach - mix of affordable and quality items',
        'items': balanced_list['items'],
        'total_cost': balanced_list['total_cost'],
        'items_count': len(balanced_list['items']),
        'remaining_budget': budget - balanced_list['total_cost']
    })
    
    return lists

def generate_cheapest_list(products, budget):
    """Generate a list focusing on the cheapest items"""
    items = []
    total_cost = 0.0
    
    for product in products:
        price = product.get('numericPrice', float('inf'))
        if price != float('inf') and total_cost + price <= budget:
            items.append(product)
            total_cost += price
    
    return {'items': items, 'total_cost': total_cost}

def generate_variety_list(products, budget):
    """Generate a list with variety across different stores"""
    items = []
    total_cost = 0.0
    stores_used = set()
    
    # First pass: one item per store
    for product in products:
        price = product.get('numericPrice', float('inf'))
        store = product.get('store', '').lower()
        
        if (price != float('inf') and 
            total_cost + price <= budget and 
            store not in stores_used):
            items.append(product)
            total_cost += price
            stores_used.add(store)
    
    # Second pass: fill remaining budget with cheapest items
    for product in products:
        price = product.get('numericPrice', float('inf'))
        
        if (price != float('inf') and 
            total_cost + price <= budget and 
            product not in items):
            items.append(product)
            total_cost += price
    
    return {'items': items, 'total_cost': total_cost}

def generate_value_list(products, budget):
    """Generate a list prioritizing discounted items and good value"""
    items = []
    total_cost = 0.0
    
    # Sort by discount availability and price
    discounted_products = []
    regular_products = []
    
    for product in products:
        if product.get('discountedPrice') or product.get('discount'):
            discounted_products.append(product)
        else:
            regular_products.append(product)
    
    # Prioritize discounted items
    all_sorted = discounted_products + regular_products
    
    for product in all_sorted:
        price = product.get('numericPrice', float('inf'))
        if price != float('inf') and total_cost + price <= budget:
            items.append(product)
            total_cost += price
    
    return {'items': items, 'total_cost': total_cost}

def generate_balanced_list(products, budget):
    """Generate a balanced list mixing affordable and mid-range items"""
    items = []
    total_cost = 0.0
    
    # Categorize products by price range
    valid_products = [p for p in products if p.get('numericPrice', float('inf')) != float('inf')]
    if not valid_products:
        return {'items': items, 'total_cost': total_cost}
    
    prices = [p['numericPrice'] for p in valid_products]
    avg_price = sum(prices) / len(prices)
    
    cheap_products = [p for p in valid_products if p['numericPrice'] <= avg_price * 0.7]
    mid_products = [p for p in valid_products if avg_price * 0.7 < p['numericPrice'] <= avg_price * 1.3]
    
    # Alternate between cheap and mid-range items
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
        
        log_and_print(f"Generating auto shopping lists for search keys: {search_keys}, budget: ${budget}")
        
        # Search all stores for all search keys
        all_products = search_all_stores(search_keys, max_results_per_store)
        
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
        shopping_lists = generate_shopping_lists(affordable_products, budget)
        
        # Add metadata to response
        response = {
            'success': True,
            'search_keys': search_keys,
            'budget': budget,
            'total_products_found': len(all_products),
            'affordable_products_count': len(affordable_products),
            'lists_generated': len(shopping_lists),
            'lists': shopping_lists,
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        return jsonify(response)
        
    except Exception as e:
        log_and_print(f"Error in auto_generated_list: {e}", 'error')
        return jsonify({
            'error': 'Internal server error', 
            'details': str(e)
        }), 500

