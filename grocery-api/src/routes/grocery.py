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
        
        if store == 'all' or store == 'aldi':
            try:
                log_and_print(f"Scraping ALDI for: {query}")
                aldi_products = fetch_aldi_products_with_discount(query, limit=min(max_results, 100))
                
                # Convert ALDI products to standard format
                for product in aldi_products:
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
        
        if store == 'all' or store == 'iga':
            try:
                log_and_print(f"Scraping IGA for: {query}")
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
        log_and_print(f"Running Node.js scraper for: {query}")
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
            log_and_print(f"Using cached results for query: {query}, store: {store}")
            all_products = search_cache[cache_key]['products']
        else:
            log_and_print(f"Fetching fresh results for query: {query}, store: {store}")
            # Fetch more results initially to reduce the need for re-scraping
            # Set a higher limit to get comprehensive results
            # if PYTHON_SCRAPERS_AVAILABLE and store in ['all', 'aldi', 'iga']:
            #     print("Using Python scrapers")
            #     scraper_result = run_python_scrapers(query, store, max_results=200)
            # else:
            #     print("Using Node.js scraper")
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
        {'id': 'aldi', 'name': 'Aldi'},
        {'id': 'woolworths', 'name': 'Woolworths'},
        {'id': 'coles', 'name': 'Coles'},
        {'id': 'iga', 'name': 'IGA'},
        {'id': 'harris', 'name': 'Harris Farm Markets'}
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

# Mock endpoint for development/testing
@grocery_bp.route('/search/mock', methods=['POST'])
@cross_origin()
def mock_search():
    """Mock search endpoint for testing with pagination"""
    data = request.get_json()
    query = data.get('query', '')
    page = data.get('page', 1)
    per_page = data.get('perPage', 10)
    
    # Generate more mock data to ensure we have at least 10+ products
    stores = ["Woolworths", "Coles", "IGA", "Harris Farm Markets", "Aldi"]
    brands = ["Brand A", "Brand B", "Premium", "Organic", "Home Brand", "Select", "Fresh"]
    categories = ["Dairy", "Bakery", "Meat", "Produce", "Pantry", "Frozen", "Organic"]
    
    all_mock_products = []
    
    # Generate 25 products to simulate a good dataset
    for i in range(25):
        store = stores[i % len(stores)]
        brand = brands[i % len(brands)]
        category = categories[i % len(categories)]
        
        # Vary prices and discounts
        base_price = 2.50 + (i * 0.30)
        has_discount = i % 3 == 0  # Every 3rd product has discount
        discount_amount = 0.20 + (i * 0.05) if has_discount else 0
        final_price = base_price - discount_amount if has_discount else base_price
        
        # Vary stock status
        in_stock = i % 8 != 0  # Every 8th product is out of stock
        
        # Store-specific colors for placeholders
        store_colors = {
            "Woolworths": "4CAF50",
            "Coles": "E53E3E", 
            "IGA": "FF9800",
            "Harris Farm Markets": "2196F3"
        }
        
        product = {
            "title": f"{brand} {query.title()} {i+1}",
            "store": store,
            "price": f"${base_price:.2f}",
            "discountedPrice": f"${final_price:.2f}" if has_discount else "",
            "discount": f"Save ${discount_amount:.2f}" if has_discount else "",
            "numericPrice": final_price,
            "inStock": in_stock,
            "unitPrice": f"${(final_price/2):.2f}/unit",
            "imageUrl": f"https://via.placeholder.com/150x150/{store_colors[store]}/white?text={store[0]}",
            "brand": brand,
            "category": category,
            "productUrl": f"https://example.com/{store.lower().replace(' ', '')}/product/{i+1}",
            "scraped_at": "2025-07-31T12:30:00Z"
        }
        all_mock_products.append(product)
    
    # Sort by price (cheapest first)
    all_mock_products.sort(key=lambda x: x['numericPrice'])
    
    # Calculate pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_products = all_mock_products[start_idx:end_idx]
    
    total_products = len(all_mock_products)
    has_more = end_idx < total_products
    
    return jsonify({
        'success': True,
        'query': query,
        'store': 'all',
        'page': page,
        'perPage': per_page,
        'totalResults': total_products,
        'currentPageResults': len(paginated_products),
        'hasMore': has_more,
        'products': paginated_products
    })

