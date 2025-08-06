const axios = require('axios');

class IGAScraper {
    constructor() {
        this.baseUrl = 'https://www.igashop.com.au/api/storefront/stores';
        this.defaultStoreId = '32600';
        this.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        };
    }

    async init() {
        // No initialization needed for API-based scraper
        return Promise.resolve();
    }

    async searchProducts(query, maxResults = 50, storeId = null) {
        try {
            const actualStoreId = storeId || this.defaultStoreId;
            const searchUrl = `${this.baseUrl}/${actualStoreId}/search`;
            const products = [];

            const params = {
                q: query,
                sort: 'price',
                take: Math.min(maxResults, 100) // API limit per request
            };

            console.log(`Searching IGA API: ${searchUrl}`);
            
            const response = await axios.get(searchUrl, {
                params: params,
                headers: this.headers
            });

            if (response.status !== 200) {
                console.error(`Failed to fetch data: HTTP ${response.status}`);
                return products;
            }

            const data = response.data;
            const totalAvailable = data.total || 0;
            const itemsReturned = data.count || 0;
            
            console.log(`API found ${totalAvailable} products but returned ${itemsReturned} items`);
            console.log(`Available facets: ${Object.keys(data.facets || {}).join(', ')}`);

            // Check if there are items in the response
            if (data.items && data.items.length > 0) {
                console.log(`Processing ${data.items.length} items...`);
                
                for (const item of data.items) {
                    if (products.length >= maxResults) break;

                    const product = this.parseProduct(item);
                    products.push(product);
                }
            } else {
                console.log("⚠️  API Limitation: The IGA search API returns metadata but no actual product items.");
                console.log("   This likely requires:");
                console.log("   - Authentication tokens");
                console.log("   - Session cookies from logged-in user");
                console.log("   - Special API keys");
                console.log("   - Different endpoint structure");
                console.log("");
                console.log("💡 Alternative approaches:");
                console.log("   1. Use the existing browser-based IGA scraper");
                console.log("   2. Reverse engineer the web app's API calls");
                console.log("   3. Contact IGA for API access");
                
                // Return empty array but with informative message
                return [];
            }

            return this.sortProductsByPrice(products);

        } catch (error) {
            console.error('Error searching IGA products:', error.message);
            if (error.response) {
                console.error(`Request error: HTTP ${error.response.status} - ${error.response.statusText}`);
            } else if (error.request) {
                console.error('Request error: No response received');
            } else {
                console.error(`Error processing response: ${error.message}`);
            }
            return [];
        }
    }

    parseProduct(item) {
        try {
            const product = {};
            
            // Basic product info matching Aldi format
            product.title = item.name || item.title || 'Unknown Product';
            product.store = 'IGA';
            
            // Handle price - IGA might have different price structure
            const priceInfo = item.price || {};
            let currentPrice, wasPrice;
            
            if (typeof priceInfo === 'object') {
                currentPrice = priceInfo.current || priceInfo.amount || null;
                wasPrice = priceInfo.was || priceInfo.originalAmount || null;
            } else {
                currentPrice = priceInfo;
                wasPrice = null;
            }
            
            // Set price fields according to Aldi format
            if (wasPrice) {
                // Product is discounted
                product.price = wasPrice;  // Original price
                product.discountedPrice = currentPrice;  // Sale price
                product.discount = wasPrice;  // For display
            } else {
                // Product is not discounted
                product.price = currentPrice;
                product.discountedPrice = null;
                product.discount = null;
            }
            
            // Extract numeric price for sorting
            product.numericPrice = this.parsePrice(currentPrice);
            
            // Image handling matching Aldi format
            product.imageUrl = this.getProductImage(item);
            
            // Additional metadata matching Aldi format
            product.productUrl = this.buildProductUrl(item);
            product.inStock = true; // Assume available if returned by API
            product.unitPrice = item.pricePerUnit || ''; // Keep unit price from IGA
            product.brand = this.extractBrand(item);
            product.category = ''; // IGA API doesn't provide category info
            
            return product;
        } catch (error) {
            console.error('Error parsing product:', error);
            return null;
        }
    }

    getProductImage(item) {
        try {
            let imageUrl = null;
            
            if (item.image) {
                if (typeof item.image === 'object') {
                    // Try different image size options in order of preference
                    imageUrl = item.image.default || 
                              item.image.details || 
                              item.image.cell || 
                              item.image.template || 
                              item.image.zoom ||
                              item.image.url || 
                              item.image.src;
                } else {
                    imageUrl = item.image;
                }
            } else if (item.imageUrl) {
                imageUrl = item.imageUrl;
            } else if (item.images && item.images.length > 0) {
                const firstImage = item.images[0];
                if (typeof firstImage === 'object') {
                    imageUrl = firstImage.default || 
                              firstImage.details || 
                              firstImage.url || 
                              firstImage.src;
                } else {
                    imageUrl = firstImage;
                }
            }
            
            return imageUrl;
        } catch (error) {
            console.error('Error getting product image:', error);
            return null;
        }
    }

    buildProductUrl(item) {
        try {
            // IGA doesn't provide direct product URLs in API
            // Could potentially construct based on product ID if available
            if (item.id) {
                return `https://www.igashop.com.au/product/${item.id}`;
            }
            return null;
        } catch (error) {
            return null;
        }
    }

    extractBrand(item) {
        try {
            // Use brand from item if available, otherwise extract from name
            if (item.brand) {
                return item.brand;
            }
            
            const productName = item.name || item.title || '';
            if (!productName) return 'IGA';
            
            // Try to extract the first word if it looks like a brand
            const words = productName.split(' ');
            const firstWord = words[0];
            
            // Simple heuristic: if first word is capitalized and not a common descriptor
            const commonDescriptors = ['fresh', 'organic', 'frozen', 'dried', 'canned', 'premium'];
            if (firstWord && 
                firstWord[0] === firstWord[0].toUpperCase() && 
                !commonDescriptors.includes(firstWord.toLowerCase())) {
                return firstWord;
            }
            
            return 'IGA'; // Default to IGA brand
        } catch (error) {
            return 'IGA';
        }
    }

    sortProductsByPrice(products) {
        return products.sort((a, b) => a.numericPrice - b.numericPrice);
    }

    parsePrice(priceStr) {
        try {
            if (!priceStr) return Infinity;
            // Remove currency symbol and convert to float
            const numericPrice = priceStr.toString().replace(/[$,]/g, '');
            return parseFloat(numericPrice) || Infinity;
        } catch (error) {
            return Infinity;
        }
    }

    useBrowserScraperAlternative(query) {
        /**
         * Demonstrates how to use the working browser-based IGA scraper
         * as an alternative to the API approach.
         */
        console.log("🔄 Using browser-based scraper as alternative...");
        console.log("   To use the working IGA scraper, run:");
        console.log(`   cd ../iga && python iga_scraper.py --query '${query}' --pages 1`);
        console.log("");
        console.log("   Or from JavaScript:");
        console.log(`   cd ../grocery-api/grocery_scraper && node index.js search '${query}' iga 10`);
        return [];
    }

    async close() {
        // No cleanup needed for API-based scraper
        return Promise.resolve();
    }

    // Utility method to get products with discount information (matching Aldi format)
    async getDiscountedProducts(query, maxResults = 50, storeId = null) {
        const products = await this.searchProducts(query, maxResults, storeId);
        return products.filter(product => product.discountedPrice);
    }

    // Method to search by specific store ID (matching Aldi format)
    async searchByLocation(query, storeId, maxResults = 50) {
        return this.searchProducts(query, maxResults, storeId);
    }

    // Static method for standalone usage
    static async search(query, maxResults = 50, storeId = null) {
        const scraper = new IGAScraper();
        await scraper.init();
        const results = await scraper.searchProducts(query, maxResults, storeId);
        await scraper.close();
        
        if (results.length === 0) {
            scraper.useBrowserScraperAlternative(query);
        } else {
            console.log(`Fetched ${results.length} products for query: '${query}'`);
            results.forEach((product, index) => {
                console.log("--->>>");
                console.log(`Product ${index + 1}:`);
                console.log(`Title: ${product.title}`);
                console.log(`Price: ${product.price}`);
                console.log(`Discounted Price: ${product.discountedPrice || 'No discount'}`);
                console.log(`Image URL: ${product.imageUrl}`);
                console.log(`Brand: ${product.brand}`);
                console.log(`Store: ${product.store}`);
                console.log(`Unit Price: ${product.unitPrice}`);
                console.log(`Product URL: ${product.productUrl || 'N/A'}`);
                console.log("---");
            });
        }
        
        return results;
    }
}

module.exports = IGAScraper;

// Command line usage
if (require.main === module) {
    const query = process.argv[2];
    if (!query) {
        console.log("Usage: node iga.js <search_query>");
        console.log("Example: node iga.js 'milk'");
        process.exit(1);
    }
    
    IGAScraper.search(query)
        .then(results => {
            if (results.length === 0) {
                console.log("No products found using the API approach.");
            }
        })
        .catch(error => {
            console.error('Error:', error.message);
            process.exit(1);
        });
}
