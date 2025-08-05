from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import subprocess
import json
import os

grocery_bp = Blueprint('grocery', __name__)

def run_node_scraper(query, store='all', max_results=20):
    """Run the Node.js scraper using subprocess"""
    try:
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
    """Search for products across all stores or a specific store using Node.js scraper"""
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
        max_results = per_page * 3  # Get more results to ensure we have enough for pagination
        
        # Validate max_results
        if max_results > 100:
            max_results = 100
        
        # Run the Node.js scraper
        scraper_result = run_node_scraper(query, store, max_results)
        
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
        
        # Apply pagination
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
            'products': paginated_products
        })
    
    except Exception as e:
        print(f"API error: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@grocery_bp.route('/stores', methods=['GET'])
@cross_origin()
def get_stores():
    """Get list of supported stores"""
    stores = [
        {'id': 'all', 'name': 'All Stores'},
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
        'scraper_available': True  # Node.js scraper is available via subprocess
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
    stores = ["Woolworths", "Coles", "IGA", "Harris Farm Markets"]
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

