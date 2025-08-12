from flask import Blueprint, request, jsonify, send_file
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask_cors import cross_origin
# subprocess import removed - no longer needed for Node.js scraper
import json
import os
import hashlib
import time
import sys
import logging
import random
# shutil import removed - no longer needed for Node.js scraper

# Import the Python scraper modules
try:
    # Try relative import first
    from ..scrapers import aldi_scrapper, iga_scrapper, harris_scrapper, coles_scrapper
    PYTHON_SCRAPERS_AVAILABLE = True
except ImportError:
    try:
        # Try absolute import if relative fails
        from scrapers import aldi_scrapper, iga_scrapper, harris_scrapper, coles_scrapper
        PYTHON_SCRAPERS_AVAILABLE = True
    except ImportError as e:
        print(f"Warning: Could not import Python scrapers: {e}")
        print("Python scrapers not available")
        aldi_scrapper = None
        iga_scrapper = None
        harris_scrapper = None
        coles_scrapper = None
        PYTHON_SCRAPERS_AVAILABLE = False

grocery_bp = Blueprint('grocery', __name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_store_logo_url(store_name, api_base_url=None):
    """
    Map store names to their logo URLs using the API endpoint
    Args:
        store_name (str): The name of the store
        api_base_url (str): Base URL for the API (optional, will auto-detect if not provided)
    Returns:
        str: URL to the store logo via API endpoint
    """
    # Normalize store name to lowercase for consistent mapping
    store_normalized = store_name.lower().strip()
    
    # Map store names to logo filenames
    logo_mapping = {
        'aldi': 'aldi.png',
        'coles': 'coles.png', 
        'woolworths': 'woolworths.png',
        'iga': 'iga.png',
        'harris': 'harris.png',
        'harris farm markets': 'harris.png'
    }
    
    # Get logo filename, default to default-store.png if not found
    logo_filename = logo_mapping.get(store_normalized, 'default-store.png')
    
    # Use provided base URL or construct default API URL
    if api_base_url is None:
        # Try to get from request context if available
        try:
            from flask import request
            if request:
                # Construct API URL from current request
                api_base_url = f"{request.scheme}://{request.host}/api/grocery"
            else:
                # Fallback to localhost for development
                api_base_url = "http://localhost:5002/api/grocery"
        except:
            # Fallback to localhost for development
            api_base_url = "http://localhost:5002/api/grocery"
    
    # Return API endpoint URL for the logo
    return f"{api_base_url}/logos/{logo_filename}"

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

def parse_iga_price_safe(price_str):
    """Safely parse IGA price strings like '$0.65 avg/ea' or '$5.99'"""
    try:
        if not price_str:
            return 0.0
        
        # Convert to string and clean
        price_str = str(price_str).strip()
        
        # Extract numeric part - look for pattern like $X.XX
        import re
        price_match = re.search(r'\$(\d+\.?\d*)', price_str)
        if price_match:
            return float(price_match.group(1))
        else:
            # Try to remove all non-numeric characters except dots
            clean_price = re.sub(r'[^\d.]', '', price_str)
            return float(clean_price) if clean_price else 0.0
    except (ValueError, AttributeError):
        return 0.0

# In-memory cache for search results
search_cache = {}
CACHE_DURATION = 300  # 5 minutes in seconds

def get_cache_key(query, store, max_results=50):
    """Generate a cache key for the search parameters"""
    return hashlib.md5(f"{query.lower()}:{store}:{max_results}".encode()).hexdigest()

def is_cache_valid(cache_entry):
    """Check if cache entry is still valid"""
    return time.time() - cache_entry['timestamp'] < CACHE_DURATION

def get_category_cache_key(category, stores, dietary_preference='none'):
    """Generate cache key for category searches"""
    stores_str = '_'.join(sorted(stores)) if isinstance(stores, list) else stores
    cache_str = f"category_{category}_{stores_str}_{dietary_preference}"
    return hashlib.md5(cache_str.encode()).hexdigest()

def run_python_scrapers(query, store='all', max_results=50, timeout_seconds=30):
    """
    Run the Python scrapers for ALDI, IGA, and Harris Farm Markets with improved error handling and store support
    
    Args:
        query (str): Search query
        store (str or list): Store name(s) to search - 'all', 'aldi', 'iga', ['aldi', 'iga'], etc.
        max_results (int): Maximum results per store
        timeout_seconds (int): Timeout for each scraper call (not implemented in Flask threads)
    
    Returns:
        dict: {'products': [...]} or {'error': 'error message'}
    """
    # Note: signal-based timeout doesn't work in Flask threads, so we'll skip timeout for now
    # This could be implemented with threading.Timer or multiprocessing if needed
    
    def normalize_store_names(store_param):
        """Convert store parameter to list of normalized store names"""
        if isinstance(store_param, list):
            stores = store_param
        elif store_param == 'all':
            stores = ['aldi', 'iga', 'harris', 'coles']
        else:
            stores = [store_param]
        
        # Normalize store names and remove -py suffix
        normalized = []
        for s in stores:
            s = s.lower().strip()
            if s.endswith('-py'):
                s = s[:-3]
            if s in ['aldi', 'iga', 'harris', 'coles']:
                normalized.append(s)
        
        return normalized
    
    def standardize_aldi_product(product):
        """Convert ALDI product to standard format"""
        try:
            # Handle discount logic properly
            current_price = product.get('price', '')
            discount_price = product.get('discount_price', '')
            
            # If there's a discount_price, that's the original price and current price is discounted
            if discount_price:
                discount_text = f"Was {discount_price}"
                display_price = current_price
            else:
                discount_text = ''
                display_price = current_price
            
            return {
                'title': product.get('name', '').strip(),
                'store': 'Aldi',
                'price': display_price,
                'discountedPrice': discount_price if discount_price else '',
                'discount': discount_text,
                'numericPrice': aldi_scrapper.aldi_parse_price(current_price) if aldi_scrapper else 0,
                'inStock': True,
                'unitPrice': '',  # Not available in ALDI API
                'imageUrl': product.get('imageUrl', product.get('image', '')),
                'brand': product.get('brand', ''),
                'category': product.get('categoryName', ''),
                'productUrl': '',  # Not available in ALDI API
                'scraped_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'scraper_source': 'python_aldi'
            }
        except Exception as e:
            log_and_print(f"Error standardizing ALDI product {product}: {e}", 'error')
            return None
    
    def standardize_iga_product(product):
        """Convert IGA product to standard format"""
        try:
            # Handle IGA price structure
            current_price = product.get('price', '')
            discount_price = product.get('discount_price', '')
            original_price = product.get('original_price', '')
            
            # Determine discount text
            discount_text = ''
            if original_price:
                discount_text = f"Was {original_price}"
            elif discount_price and discount_price != current_price:
                discount_text = f"Was {discount_price}"
            
            return {
                'title': product.get('name', '').strip(),
                'store': 'IGA',
                'price': str(current_price),
                'discountedPrice': original_price if original_price else discount_price,
                'discount': discount_text,
                'numericPrice': parse_iga_price_safe(str(current_price)),
                'inStock': product.get('available', True),
                'unitPrice': product.get('unitPrice', product.get('pricePerUnit', '')),
                'imageUrl': product.get('image', product.get('imageUrl', '')),
                'brand': product.get('brand', ''),
                'category': '',  # Not readily available in IGA API
                'productUrl': '',  # Not available in IGA API
                'scraped_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'scraper_source': 'python_iga'
            }
        except Exception as e:
            log_and_print(f"Error standardizing IGA product {product}: {e}", 'error')
            return None
    
    def standardize_harris_product(product):
        """Convert Harris product to standard format"""
        try:
            # Harris scraper already returns in a good format, just need minor adjustments
            main_price = product.get('price', '')
            
            return {
                'title': product.get('title', '').strip(),
                'store': product.get('store', 'Harris Farm Markets'),
                'price': main_price,
                'discountedPrice': product.get('discountedPrice', ''),
                'discount': product.get('discount', ''),
                'numericPrice': product.get('numericPrice', 0),
                'inStock': product.get('inStock', True),
                'unitPrice': product.get('unitPrice', ''),
                'unitPriceText': product.get('unitPriceText', ''),
                'imageUrl': product.get('imageUrl', ''),
                'brand': product.get('brand', ''),
                'category': product.get('category', ''),
                'productUrl': product.get('productUrl', ''),
                'scraped_at': product.get('scraped_at', time.strftime('%Y-%m-%dT%H:%M:%SZ')),
                'scraper_source': 'python_harris'
            }
        except Exception as e:
            log_and_print(f"Error standardizing Harris product {product}: {e}", 'error')
            return None
    
    def standardize_coles_product(product):
        """Convert Coles product to standard format"""
        try:
            # Coles scraper returns products in a consistent format
            main_price = product.get('price', '')
            
            return {
                'title': product.get('name', '').strip(),
                'store': product.get('store', 'Coles'),
                'price': main_price,
                'discountedPrice': product.get('discount_price', ''),
                'discount': product.get('discount_amount', ''),
                'numericPrice': product.get('price_numeric', 0),
                'inStock': True,  # Coles file-based scraper assumes in stock
                'unitPrice': product.get('per_unit_price', ''),
                'unitPriceText': product.get('per_unit_price', ''),
                'imageUrl': product.get('imageUrl', ''),
                'brand': product.get('brand', ''),
                'category': product.get('category', ''),
                'productUrl': product.get('productUrl', ''),
                'scraped_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'scraper_source': 'python_coles',
                'weight_size': product.get('weight_size', ''),
                'original_price': product.get('original_price', ''),
                'discount_percentage': product.get('discount_percentage', '')
            }
        except Exception as e:
            log_and_print(f"Error standardizing Coles product {product}: {e}", 'error')
            return None
    
    try:
        all_products = []
        stores_to_search = normalize_store_names(store)
        scraper_errors = []
        
        log_and_print(f"Python scrapers starting for query '{query}' in stores: {stores_to_search}")
        
        # Scrape ALDI if requested
        if 'aldi' in stores_to_search and aldi_scrapper:
            try:
                log_and_print(f"0001 Scraping ALDI Python API for: {query} with max_results {max_results}")
                
                aldi_products = aldi_scrapper.fetch_aldi_products_with_discount(
                    query, 
                    limit=min(max_results, 50)
                )
                
                if aldi_products:
                    # Enforce max_results across paginated results
                    if len(aldi_products) > max_results:
                        log_and_print(f"ALDI returned {len(aldi_products)} raw products; capping to max_results={max_results}")
                        aldi_products = aldi_products[:max_results]
                    log_and_print(f"ALDI returned {len(aldi_products)} raw products")
                    
                    # Convert to standard format
                    for product in aldi_products:
                        standardized = standardize_aldi_product(product)
                        if standardized:
                            all_products.append(standardized)
                    
                    log_and_print(f"ALDI: {len([p for p in all_products if p.get('store') == 'Aldi'])} products standardized")
                else:
                    log_and_print("ALDI Python API returned no products - API may have restrictions")
                    scraper_errors.append("ALDI: API returned no products (possible API changes or restrictions)")
                    
            except Exception as e:
                error_msg = f"ALDI scraper failed: {str(e)}"
                log_and_print(error_msg, 'error')
                scraper_errors.append(f"ALDI: {error_msg}")
                # Note: ALDI API may have changed or require additional authentication
        
        # Scrape IGA if requested
        if 'iga' in stores_to_search and iga_scrapper:
            try:
                log_and_print(f"Scraping IGA Python API for: {query}")
                
                iga_products = iga_scrapper.fetch_iga_products(
                    query, 
                    limit=min(max_results, 100)
                )
                
                if iga_products:
                    # Enforce max_results to be consistent with API contract
                    if len(iga_products) > max_results:
                        log_and_print(f"IGA returned {len(iga_products)} raw products; capping to max_results={max_results}")
                        iga_products = iga_products[:max_results]
                    log_and_print(f"IGA returned {len(iga_products)} raw products")
                    
                    # Convert to standard format
                    for product in iga_products:
                        standardized = standardize_iga_product(product)
                        if standardized:
                            all_products.append(standardized)
                    
                    log_and_print(f"IGA: {len([p for p in all_products if p.get('store') == 'IGA'])} products standardized")
                else:
                    log_and_print("IGA returned no products")
                    
            except Exception as e:
                error_msg = f"IGA scraper failed: {str(e)}"
                log_and_print(error_msg, 'error')
                scraper_errors.append(f"IGA: {error_msg}")
        
        # Scrape Harris if requested
        if 'harris' in stores_to_search and harris_scrapper:
            try:
                log_and_print(f"Scraping Harris Farm Markets for: {query}")
                
                harris_products = harris_scrapper.fetch_harris_products(
                    query, 
                    max_results=min(max_results, 100)
                )
                
                if harris_products:
                    # Enforce max_results to be consistent with API contract
                    if len(harris_products) > max_results:
                        log_and_print(f"Harris returned {len(harris_products)} raw products; capping to max_results={max_results}")
                        harris_products = harris_products[:max_results]
                    log_and_print(f"Harris returned {len(harris_products)} raw products")
                    
                    # Convert to standard format
                    for product in harris_products:
                        standardized = standardize_harris_product(product)
                        if standardized:
                            all_products.append(standardized)
                    
                    log_and_print(f"Harris: {len([p for p in all_products if p.get('store') == 'Harris Farm Markets'])} products standardized")
                else:
                    log_and_print("Harris returned no products")
                    
            except Exception as e:
                error_msg = f"Harris scraper failed: {str(e)}"
                log_and_print(error_msg, 'error')
                scraper_errors.append(f"Harris: {error_msg}")
        
        # Scrape Coles if requested
        if 'coles' in stores_to_search and coles_scrapper:
            try:
                log_and_print(f"Scraping Coles for: {query}")
                
                coles_products = coles_scrapper.fetch_coles_products_from_file(
                    query, 
                    limit=min(max_results, 100)
                )
                
                if coles_products:
                    # Enforce max_results to be consistent with API contract
                    if len(coles_products) > max_results:
                        log_and_print(f"Coles returned {len(coles_products)} raw products; capping to max_results={max_results}")
                        coles_products = coles_products[:max_results]
                    log_and_print(f"Coles returned {len(coles_products)} raw products")
                    
                    # Convert to standard format
                    for product in coles_products:
                        standardized = standardize_coles_product(product)
                        if standardized:
                            all_products.append(standardized)
                    
                    log_and_print(f"Coles: {len([p for p in all_products if p.get('store') == 'Coles'])} products standardized")
                else:
                    log_and_print("Coles returned no products")
                    
            except Exception as e:
                error_msg = f"Coles scraper failed: {str(e)}"
                log_and_print(error_msg, 'error')
                scraper_errors.append(f"Coles: {error_msg}")
        
        # Remove any None values from failed standardizations
        all_products = [p for p in all_products if p is not None]
        
        # Sort by price (cheapest first)
        try:
            all_products.sort(key=lambda x: x.get('numericPrice', float('inf')))
        except Exception as e:
            log_and_print(f"Error sorting products by price: {e}", 'warning')
        
        result = {
            'products': all_products,
            'total_products': len(all_products),
            'stores_searched': stores_to_search,
            'query': query
        }
        
        # Add error information if there were any
        if scraper_errors:
            result['warnings'] = scraper_errors
            log_and_print(f"Python scrapers completed with warnings: {scraper_errors}", 'warning')
        
        log_and_print(f"Python scrapers completed successfully: {len(all_products)} total products from {len(stores_to_search)} stores")
        return result
        
    except Exception as e:
        error_msg = f"Python scrapers failed completely: {str(e)}"
        log_and_print(error_msg, 'error')
        return {"error": error_msg}

# Note: Node.js scraper function removed - now using Python scrapers only

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
        
        store = data.get('store', 'all').lower()
        # Validate store parameter
        valid_stores = ['aldi', 'iga', 'coles']  # All stores supported via Python scrapers
        if store not in valid_stores and store != 'all':
            return jsonify({
                'error': f'Invalid store "{store}". Supported stores: {", ".join(valid_stores)} or "all"'
            }), 400
        
        page = data.get('page', 1)
        per_page = data.get('perPage', 10)
        max_results = data.get('max_results', 50)  # Get max_results from request or default to 50
        
        # Generate cache key
        cache_key = get_cache_key(query, store, max_results)
        
        # Check if we have cached results that are still valid
        if cache_key in search_cache and is_cache_valid(search_cache[cache_key]):
            log_and_print(f"LN-199: Using cached results for query: {query}, store: {store}")
            all_products = search_cache[cache_key]['products']
        else:
            log_and_print(f"LN-201: Fetching fresh results for query: {query}, store: {store}")
            
            # Priority: Use Python scrapers for ALDI, IGA, and Harris Farm Markets
            scraper_result = {"products": []}
            
            # Always use Node.js scraper for production reliability
            # Only use Python scrapers if specifically requested with -py suffix
            if PYTHON_SCRAPERS_AVAILABLE and store in ['aldi-py', 'iga-py']:
                log_and_print("Using Python scrapers (explicitly requested)")
                python_store = store.replace('-py', '')  # Convert aldi-py -> aldi
                scraper_result = run_python_scrapers(query, python_store, max_results=max_results)
                
                if 'error' in scraper_result:
                    log_and_print(f"Python scrapers failed: {scraper_result['error']}")
                    scraper_result = {"products": []}  # Reset to try Node.js
                elif scraper_result.get('products'):
                    log_and_print(f"Python scrapers returned {len(scraper_result['products'])} products")
                else:
                    log_and_print("Python scrapers returned no products")
            
            # Use Python scrapers for ALDI, IGA, and Harris Farm Markets
            if not scraper_result.get('products'):
                # Determine which stores to scrape
                stores_to_scrape = []
                if store == 'all':
                    stores_to_scrape = ['aldi', 'iga', 'coles']
                elif store in ['aldi', 'iga', 'coles']:
                    stores_to_scrape = [store]
                
                if stores_to_scrape:
                    log_and_print(f"Using Python scrapers for stores: {stores_to_scrape}")
                    python_result = run_python_scrapers(query, stores_to_scrape, max_results=max_results)
                    
                    if 'error' not in python_result and python_result.get('products'):
                        scraper_result = python_result
                        log_and_print(f"Python scrapers returned {len(python_result['products'])} products")
                    else:
                        log_and_print(f"Python scrapers failed or returned no products: {python_result.get('error', 'No products')}")
                        # If we have warnings but no error, check if it's just ALDI API issues
                        if python_result.get('warnings') and not python_result.get('error'):
                            scraper_result = python_result  # Return what we have, even if empty
                        else:
                            scraper_result = {"error": f"No products found for {store}. {python_result.get('error', '')}"}

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
                store_name = p.get("store", store)
                product = {
                    "title": p.get("title", "N/A"),
                    "store": store_name,  # Use the actual store from scraped product, fallback to request store
                    "store_logo": get_store_logo_url(store_name),  # Add store logo URL
                    "price": p.get("price", f"${p.get('numericPrice', 0):.2f}"),
                    "discountedPrice": p.get("discountedPrice", ""),
                    "discount": p.get("discount", ""),
                    "numericPrice": p.get("numericPrice", 0),
                    "inStock": p.get("inStock", True),  # Use actual inStock value from scraper
                    "unitPrice": p.get("unitPrice", ""),
                    "imageUrl": p.get("imageUrl", ""),
                    "brand": p.get("brand", ""),
                    "category": p.get("category", ""),
                    "productUrl": p.get("productUrl", ""),
                    "scraped_at": p.get("scraped_at", "")
                }

                # Use discount field from scraper if not already set
                if not product["discount"] and p.get("discount"):
                    product["discount"] = p.get("discount")

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
        {'id': 'aldi', 'name': 'ALDI'},
        {'id': 'iga', 'name': 'IGA'},
        {'id': 'coles', 'name': 'Coles'},
    ]
    
    return jsonify({
        'success': True,
        'stores': stores,
        'message': 'ALDI, IGA, Coles, and Harris Farm Markets are supported via Python scrapers (ALDI may have API limitations)'
    })

@grocery_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Health check endpoint"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    return jsonify({
        'success': True,
        'status': 'healthy',
        'python_scrapers_available': PYTHON_SCRAPERS_AVAILABLE,
        'supported_stores': ['aldi', 'iga', 'harris'] if PYTHON_SCRAPERS_AVAILABLE else [],
        'supported_categories': ['fruits', 'vegetables', 'dairy', 'meat', 'bakery', 'pantry', 'snacks', 'beverages', 'frozen', 'seafood', 'breakfast', 'healthy'],
        'scraper_info': 'Using Python scrapers for ALDI, IGA, and Harris Farm Markets. Node.js scrapers have been removed.',
        'current_directory': current_dir,
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

@grocery_bp.route('/test-scraper', methods=['POST'])
@cross_origin()
def test_scraper():
    """Test Python scraper directly for debugging"""
    try:
        data = request.get_json()
        query = data.get('query', 'milk')
        store = data.get('store', 'iga')
        
        log_and_print(f"Testing Python scraper with query='{query}', store='{store}'")
        
        # Only IGA is supported
        if store == 'iga':
            log_and_print(f"Testing Python scraper for {store}")
            result = run_python_scrapers(query, ['iga'], max_results=5)
        else:
            log_and_print(f"Store '{store}' is not supported")
            result = {"error": f"Store '{store}' is not supported. Only IGA is available."}
        
        return jsonify({
            'success': True,
            'test_query': query,
            'test_store': store,
            'scraper_result': result,
            'result_type': type(result).__name__,
            'has_products': 'products' in result if isinstance(result, dict) else False,
            'product_count': len(result.get('products', [])) if isinstance(result, dict) and 'products' in result else 0,
            'supported_stores': ['iga']
        })
        
    except Exception as e:
        log_and_print(f"Error in test_scraper: {e}", 'error')
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

def search_all_stores(search_keys, max_results_per_store=50, selected_stores=None):
    """Search ALDI, IGA, and Harris Farm Markets stores for the given search keys"""
    if selected_stores is None or len(selected_stores) == 0:
        # Default to all supported stores
        search_stores = ['aldi', 'iga', 'harris', 'coles']
    else:
        # Only keep supported stores from selected stores
        search_stores = [store for store in selected_stores if store in ['aldi', 'iga', 'harris', 'coles', 'all']]
        if 'all' in selected_stores:
            search_stores = ['aldi', 'iga', 'harris', 'coles']
        elif not search_stores:
            log_and_print("No supported stores in selection. ALDI, IGA, Coles, and Harris Farm Markets are supported.", 'warning')
            return []
    
    all_products = []
    
    for search_key in search_keys:
        log_and_print(f"Searching stores {search_stores} for: {search_key}")
        
        # Use Python scrapers for supported stores
        if PYTHON_SCRAPERS_AVAILABLE:
            log_and_print(f"Using Python scrapers for stores: {search_stores}")
            python_result = run_python_scrapers(search_key, search_stores, max_results_per_store)
            
            if 'products' in python_result:
                all_products.extend(python_result['products'])
                log_and_print(f"Python scrapers added {len(python_result['products'])} products")
            elif 'error' in python_result:
                log_and_print(f"Python scrapers failed: {python_result['error']}", 'warning')
        else:
            log_and_print("Python scrapers not available", 'error')
    
    # Remove duplicates based on title and store
    seen = set()
    unique_products = []
    for product in all_products:
        key = f"{product.get('title', '').lower()}_{product.get('store', '').lower()}"
        if key not in seen:
            seen.add(key)
            # Add store logo if not already present
            if 'store_logo' not in product and 'store' in product:
                product['store_logo'] = get_store_logo_url(product['store'])
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

@grocery_bp.route('/store/<store_name>', methods=['POST'])
@cross_origin()
def search_store_products(store_name):
    """Search for multiple products in a specific store, returning 10 cheapest items for each search term"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        search_terms = data.get('search_terms', [])
        dietary_preference = data.get('dietary_preference', 'none')
        page = data.get('page', 1)
        per_page = data.get('perPage', 10)
        
        # Get max_results from request or use default based on store
        if(store_name in ['iga', 'aldi']):
            max_results = data.get('max_results', 10)  # Default 10 for IGA/ALDI/Harris
            dietary_search_terms = {
                'none': [
                    # General groceries - any food items (non-veg and veg)
                    'milk', 'eggs', 'rice', 'pasta', 
                    'yogurt', 'fruit', 'vegetables', 'meat', 'dairy',
                    'grocery',
                ],  
                'vegetarian': [
                    'vegetarian protein', 'tofu', 'beans', 'lentils', 'vegetarian curry', 'vegetarian soup', 'nuts', 'seeds',
                    'vegetables'
                ],
                'vegan': [
                    'vegan protein', 'tofu', 'tempeh', 'vegan cheese', 'milk', 'yeast', 'yogurt', 'agave', 'maple syrup', 'cashew cream'
                ],
                'gluten free': [
                    'gluten free', 'rice', 'flour',  'rice cakes', 'corn tortillas', 'rice noodles'
                ],
                'others': [
                    'bread', 'milk', 'eggs', 'rice', 'pasta', 
                    'yogurt', 'cereal', 'fruit', 'vegetables', 'meat', 
                    'grocery',
                ]
            }
        else:
            max_results = data.get('max_results', 50)  # Default 50 for other stores
            dietary_search_terms = {
                'none': [
                    'grocery'
                ],  
                'vegetarian': [
                    'vegetarian'
                ],
                'vegan': [
                    'vegan'
                ],
                'gluten free': [
                    'gluten free'
                ],
                'others': [
                    'others'
                ]
            }
        # Use client-provided search_terms if present; otherwise use dietary preference defaults
        if not search_terms:
            if dietary_preference in dietary_search_terms:
                search_terms = dietary_search_terms[dietary_preference]
                log_and_print(f"Using dietary preference '{dietary_preference}' with {len(search_terms)} search terms")
            else:
                return jsonify({'error': f'Invalid dietary_preference "{dietary_preference}". Supported: none, vegetarian, vegan, gluten free, others'}), 400
        
        # Validate store name
        store_name = store_name.lower().strip()
        valid_stores = ['aldi', 'iga', 'harris', 'coles']
        if store_name not in valid_stores:
            return jsonify({
                'error': f'Invalid store "{store_name}". Supported stores: {", ".join(valid_stores)}'
            }), 400
        
        log_and_print(f"Searching {store_name} for multiple terms: {search_terms}")
        
        all_products = []
        search_term_stats = []

        def scrape_single_term(search_term: str):
            term = search_term.strip()
            if not term:
                return [], {
                    'search_term': term,
                    'total_found': 0,
                    'products_returned': 0,
                    'error': 'empty term'
                }

            if store_name in ['aldi', 'iga', 'harris', 'coles']:
                log_and_print(f"line 1290: Using Python scraper for '{store_name}' for '{term}' with max_results '{max_results}'")
                scraper_result = run_python_scrapers(term, [store_name], max_results)
            else:
                log_and_print(f"Store '{store_name}' is not supported")
                return [], {
                    'search_term': term,
                    'total_found': 0,
                    'products_returned': 0,
                    'error': f"Store '{store_name}' is not supported"
                }

            if 'error' in scraper_result:
                log_and_print(f"Error searching for {term} in {store_name}: {scraper_result['error']}", 'error')
                return [], {
                    'search_term': term,
                    'total_found': 0,
                    'products_returned': 0,
                    'error': scraper_result['error']
                }

            if 'products' in scraper_result:
                raw_products = scraper_result['products']
            elif isinstance(scraper_result, list):
                raw_products = scraper_result
            else:
                raw_products = []

            processed_products = []
            for p in raw_products:
                store_name_from_product = p.get("store", store_name)
                product = {
                    "title": p.get("title", "N/A"),
                    "store": store_name_from_product,
                    "store_logo": get_store_logo_url(store_name_from_product),
                    "price": p.get("price", f"${p.get('numericPrice', 0):.2f}"),
                    "discountedPrice": p.get("discountedPrice", ""),
                    "discount": p.get("discount", ""),
                    "numericPrice": p.get("numericPrice", 0),
                    "inStock": p.get("inStock", True),
                    "unitPrice": p.get("unitPrice", ""),
                    "imageUrl": p.get("imageUrl", ""),
                    "brand": p.get("brand", ""),
                    "category": p.get("category", ""),
                    "productUrl": p.get("productUrl", ""),
                    "search_term": term,
                    "scraped_at": p.get("scraped_at", time.strftime('%Y-%m-%dT%H:%M:%SZ'))
                }
                if product["numericPrice"] > 0:
                    processed_products.append(product)

            stat = {
                'search_term': term,
                'total_found': len(processed_products),
                'products_returned': len(processed_products)
            }
            log_and_print(f"Found {len(processed_products)} total, returning all {len(processed_products)} products for '{term}' in {store_name}")
            return processed_products, stat

        # Parallelize scraping across search terms
        max_workers = min(8, len(search_terms)) if search_terms else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(scrape_single_term, t) for t in search_terms]
            for future in as_completed(futures):
                try:
                    products_result, stat_result = future.result()
                    all_products.extend(products_result)
                    search_term_stats.append(stat_result)
                except Exception as e:
                    log_and_print(f"Worker error: {e}", 'error')
        
        
        return jsonify({
            'success': True,
            'store': store_name,
            'store_logo': get_store_logo_url(store_name),
            'dietary_preference': dietary_preference,
            'search_terms': search_terms,
            'search_term_stats': search_term_stats,
            'total_products': len(all_products),
            'products': all_products,
            'scraped_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')
        })
        
    except Exception as e:
        log_and_print(f"Error in search_store_products: {e}", 'error')
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@grocery_bp.route('/categories', methods=['GET'])
@cross_origin()
def get_categories():
    """Get list of available grocery categories with images"""
    try:
        # Define predefined categories with appropriate images
        categories = [
            {
                "id": "fruits",
                "name": "Fruits",
                "image": "https://images.unsplash.com/photo-1610832958506-aa56368176cf?q=80&w=200&auto=format&fit=crop",
                "description": "Fresh fruits and seasonal produce"
            },
            {
                "id": "vegetables", 
                "name": "Vegetables",
                "image": "https://images.unsplash.com/photo-1557844352-761f2565b576?q=80&w=200&auto=format&fit=crop",
                "description": "Fresh vegetables and greens"
            },
            {
                "id": "dairy",
                "name": "Dairy",
                "image": "https://images.unsplash.com/photo-1628088062854-d1870b4553da?q=80&w=200&auto=format&fit=crop",
                "description": "Milk, cheese, yogurt and dairy products"
            },
            {
                "id": "meat",
                "name": "Meat & Poultry",
                "image": "https://images.unsplash.com/photo-1467825487722-2a7c4cd62e75?w=900&auto=format&fit=crop&q=60",
                "description": "Fresh meat, chicken, and poultry"
            },
            {
                "id": "bakery",
                "name": "Bakery",
                "image": "https://images.unsplash.com/photo-1608198093002-ad4e005484ec?w=900&auto=format&fit=crop&q=60",
                "description": "Fresh bread, pastries and baked goods"
            },
            {
                "id": "pantry",
                "name": "Pantry Staples",
                "image": "https://images.unsplash.com/photo-1590779033100-9f60a05a013d?w=900&auto=format&fit=crop&q=60",
                "description": "Rice, pasta, grains and pantry essentials"
            },
            {
                "id": "snacks",
                "name": "Snacks",
                "image": "https://images.unsplash.com/photo-1621939514649-280e2ee25f60?w=900&auto=format&fit=crop&q=60",
                "description": "Chips, nuts, crackers and snack foods"
            },
            {
                "id": "beverages",
                "name": "Beverages",
                "image": "https://images.unsplash.com/photo-1595981267035-7b04ca84a82d?w=900&auto=format&fit=crop&q=60",
                "description": "Juices, soft drinks and beverages"
            },
            {
                "id": "frozen",
                "name": "Frozen Foods",
                "image": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=900&auto=format&fit=crop&q=60",
                "description": "Frozen vegetables, meals and ice cream"
            },
            {
                "id": "seafood",
                "name": "Seafood",
                "image": "https://images.unsplash.com/photo-1565680018434-b513d5573b07?w=900&auto=format&fit=crop&q=60",
                "description": "Fresh fish and seafood"
            },
            {
                "id": "breakfast",
                "name": "Breakfast",
                "image": "https://images.unsplash.com/photo-1533089860892-a7c6f0a88110?w=900&auto=format&fit=crop&q=60",
                "description": "Cereals, oats and breakfast items"
            },
            {
                "id": "healthy",
                "name": "Health & Organic",
                "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=900&auto=format&fit=crop&q=60",
                "description": "Organic and health food products"
            }
        ]
        
        return jsonify({
            'success': True,
            'categories': categories,
            'total_categories': len(categories),
            'message': f'{len(categories)} categories available'
        })
        
    except Exception as e:
        log_and_print(f"Error in get_categories: {e}", 'error')
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@grocery_bp.route('/category/<category_name>', methods=['POST'])
@cross_origin()
def search_category_products(category_name):
    """Search for products in a specific category across all supported stores with pagination"""
    try:
        data = request.get_json()
        
        # Get parameters with defaults
        max_results = data.get('max_results', 20) if data else 20
        dietary_preference = data.get('dietary_preference', 'none') if data else 'none'
        fast_mode = data.get('fast_mode', False) if data else False
        
        # Use fast mode with only Coles for quicker results, or all stores for comprehensive results
        if fast_mode:
            stores = data.get('stores', ['coles']) if data else ['coles']
        else:
            stores = data.get('stores', ['aldi', 'iga', 'harris', 'coles']) if data else ['aldi', 'iga', 'harris', 'coles']
        
        page = data.get('page', 1) if data else 1
        per_page = data.get('per_page', 10) if data else 10
        
        # Check cache first
        cache_key = get_category_cache_key(category_name, stores, f"{dietary_preference}_{fast_mode}")
        if cache_key in search_cache and is_cache_valid(search_cache[cache_key]):
            log_and_print(f"Cache hit for category '{category_name}' with stores {stores}")
            cached_result = search_cache[cache_key]['data']
            all_products = cached_result.get('products', [])
            search_term = cached_result.get('search_term', category_name.lower())
        else:
            # Cache miss - need to scrape
            log_and_print(f"Cache miss for category '{category_name}' - performing fresh search")
            
            # Use the category name directly as the search term
            search_term = category_name.lower()
            
            # Apply dietary preference modifiers to the search term
            if dietary_preference == 'vegetarian':
                if category_name.lower() == 'meat':
                    search_term = 'vegetarian protein'
                else:
                    search_term = f"vegetarian {category_name.lower()}"
                    
            elif dietary_preference == 'vegan':
                if category_name.lower() == 'dairy':
                    search_term = 'plant based dairy'
                elif category_name.lower() == 'meat':
                    search_term = 'vegan protein'
                else:
                    search_term = f"vegan {category_name.lower()}"
                    
            elif dietary_preference == 'gluten free':
                search_term = f"gluten free {category_name.lower()}"
            
            log_and_print(f"Searching category '{category_name}' with search term: '{search_term}' (dietary: {dietary_preference})")
            log_and_print(f"Using max 30 products per store for category search across stores: {stores}")
            
            all_products = []
            
            # Search the category name across supported stores using the existing Python scrapers
            try:
                # Use run_python_scrapers to search across all stores
                # Limit each store to 30 products maximum for category searches (per user request)
                max_results_per_store = 30
                log_and_print(f"Calling scrapers with max_results_per_store={max_results_per_store}")
                scraper_result = run_python_scrapers(
                    search_term, 
                    stores, 
                    max_results=max_results_per_store
                )
                
                if 'products' in scraper_result and scraper_result['products']:
                    # Add category metadata to products
                    for product in scraper_result['products']:
                        product['category'] = category_name
                        product['search_term'] = search_term
                    
                    all_products.extend(scraper_result['products'])
                    log_and_print(f"Found {len(scraper_result['products'])} products for category '{category_name}'")
                    
            except Exception as e:
                log_and_print(f"Error searching for category '{category_name}': {e}", 'warning')
            
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
            
            # Cache the results
            search_cache[cache_key] = {
                'timestamp': time.time(),
                'data': {
                    'products': unique_products,
                    'search_term': search_term
                }
            }
            log_and_print(f"Cached results for category '{category_name}' with {len(unique_products)} products")
            all_products = unique_products
        
        # Apply pagination
        total_products = len(all_products)
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_products = all_products[start_index:end_index]
        
        # Calculate pagination info
        total_pages = (total_products + per_page - 1) // per_page  # Ceiling division
        has_next = page < total_pages
        has_prev = page > 1
        
        # Get category info
        category_info = {
            'id': category_name.lower(),
            'name': category_name.title(),
            'total_products': len(paginated_products)
        }
        
        return jsonify({
            'success': True,
            'category': category_info,
            'dietary_preference': dietary_preference,
            'search_term': search_term,
            'stores_searched': stores,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_products,
                'total_pages': total_pages,
                'has_next': has_next,
                'has_prev': has_prev
            },
            'total_products': len(paginated_products),
            'products': paginated_products,
            'scraped_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')
        })
        
    except Exception as e:
        log_and_print(f"Error in search_category_products: {e}", 'error')
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@grocery_bp.route('/logos/<logo_name>', methods=['GET'])
@cross_origin()
def serve_logo(logo_name):
    """Serve store logo images"""
    try:
        # Get the path to the local logos directory within grocery-api
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logos_path = os.path.join(current_dir, '..', '..', 'logos')
        logo_file_path = os.path.join(logos_path, logo_name)
        
        # Check if file exists and is a valid image file
        if not os.path.exists(logo_file_path):
            # Return default store logo if specific logo not found
            default_logo_path = os.path.join(logos_path, 'default-store.png')
            if os.path.exists(default_logo_path):
                return send_file(default_logo_path, mimetype='image/png')
            else:
                return jsonify({'error': 'Logo not found'}), 404
        
        # Determine MIME type based on file extension
        _, ext = os.path.splitext(logo_name.lower())
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }
        
        mimetype = mime_types.get(ext, 'image/png')
        
        return send_file(logo_file_path, mimetype=mimetype)
        
    except Exception as e:
        log_and_print(f"Error serving logo {logo_name}: {e}", 'error')
        return jsonify({'error': 'Internal server error'}), 500

