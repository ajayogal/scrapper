import requests
import time
import sys

def fetch_aldi_products_with_discount(query, limit=30, service_point='G452'):
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
def parse_price(price_str):
    # Converts '$1.99' to float 1.99
    return float(price_str.replace('$', '')) if price_str else float('inf')

# Usage example
if __name__ == '__main__':
    # Check if query is provided as command line argument
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        # Fallback to user input if no command line argument
        query = input("Enter search query: ").strip()
        if not query:
            print("No query provided. Exiting.")
            sys.exit(1)
    
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
