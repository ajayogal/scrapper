import requests
import time

def fetch_iga_products(query, limit=30, store_id='32600'):
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
    # base_url = f"https://www.igashop.com.au/api/storefront/stores/{store_id}/search?q=fruits&sort=price&take=100"
    
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
                
                # Handle image URL
                image_url = None
                if 'image' in item:
                    if isinstance(item['image'], dict):
                        image_url = item['image'].get('url', item['image'].get('src'))
                    else:
                        image_url = item['image']
                elif 'imageUrl' in item:
                    image_url = item['imageUrl']
                elif 'images' in item and len(item['images']) > 0:
                    first_image = item['images'][0]
                    if isinstance(first_image, dict):
                        image_url = first_image.get('url', first_image.get('src'))
                    else:
                        image_url = first_image
                
                product['image'] = image_url
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
    query = 'banana'
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
            print(f"Store: {product['store']}")
            print("---")
    else:
        print("No products found using the API approach.")
        print("")
        use_browser_scraper_alternative(query)
