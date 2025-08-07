

import os
import json
from flask import Blueprint, jsonify

merger_bp = Blueprint('merger', __name__)

def merge_json_files(folder_name):
    input_dir = f"downloads/{folder_name.lower()}_products"
    output_dir = "generated"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_file = f"{output_dir}/{folder_name.lower()}_merged_products.json"
    report_file = f"{output_dir}/{folder_name.lower()}_products_report.txt"
    
    unique_products = {}
    duplicate_counts = {}
    total_items = 0
    desired_keys = [
        "title", "current_price", "original_price", "discount_percentage",
        "discount_amount", "image_url", "product_url", "category", "brand",
        "weight_size", "per_unit_price"
    ]
    
    for filename in os.listdir(input_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(input_dir, filename)
            with open(filepath, 'r') as f:
                try:
                    data = json.load(f)
                    if "products" in data and isinstance(data["products"], list):
                        for product in data["products"]:
                            total_items += 1
                            url = product.get("product_url")
                            title = product.get("title", "No Title")
                            if url:
                                if url not in unique_products:
                                    filtered_product = {key: product.get(key) for key in desired_keys}
                                    unique_products[url] = filtered_product
                                else:
                                    duplicate_counts[title] = duplicate_counts.get(title, 1) + 1
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from {filename}")

    with open(output_file, 'w') as f:
        json.dump(list(unique_products.values()), f, indent=2)

    with open(report_file, 'w') as f:
        f.write("--- Unique Items ---\n")
        unique_titles = [p['title'] for p in unique_products.values() if p.get('title') not in duplicate_counts]
        for title in unique_titles:
            f.write(f"{title}\n")

        f.write("\n--- Duplicate Items ---\n")
        if not duplicate_counts:
            f.write("No duplicate items found.\n")
        else:
            for title, count in duplicate_counts.items():
                f.write(f"{title} (Duplicate Count: {count})\n")
        f.write(f"\n\nSuccessfully merged {len(unique_products)} unique items from a total of {total_items} items processed. \n\n")

    return f"Successfully merged {len(unique_products)} unique items from a total of {total_items} items processed. Report generated at {report_file}"

@merger_bp.route('/<string:folder_name>', methods=['POST'])
def merge_jsons(folder_name):
    try:
        message = merge_json_files(folder_name)
        return jsonify({"message": message}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

