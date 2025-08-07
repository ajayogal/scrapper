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

    // Fetch special products using promotional search terms
    async fetchSpecialProducts(limitPerPage = 100, targetProducts = 500, storeId = null) {
        try {
            const actualStoreId = storeId || this.defaultStoreId;
            const searchUrl = `${this.baseUrl}/${actualStoreId}/search`;
            
            const products = [];
            let specialProductCount = 0;
            
            // Search terms that typically yield promotional/special products
            const promotionalQueries = [
                "special",      // Items on special
                "half price",   // Half price items  
                "sale",         // Sale items
                "offer",        // Special offers
                "discount",     // Discounted items
                "promo",        // Promotional items
                "deal",         // Deal items
                "save",         // Save money items
                "reduced",      // Reduced price items
                "clearance"     // Clearance items
            ];
            
            console.log(`Starting to fetch IGA special products using promotional search terms (target: ${targetProducts})...`);
            console.log(`Will search for: ${promotionalQueries.join(', ')}`);
            
            for (let queryIdx = 0; queryIdx < promotionalQueries.length; queryIdx++) {
                if (specialProductCount >= targetProducts) {
                    break;
                }
                
                const query = promotionalQueries[queryIdx];
                console.log(`\n--- Searching for '${query}' products (${queryIdx + 1}/${promotionalQueries.length}) ---`);
                
                // Search with current promotional term
                const params = {
                    q: query,
                    take: limitPerPage
                };
                
                const response = await axios.get(searchUrl, {
                    params: params,
                    headers: this.headers,
                    timeout: 10000
                });
                
                if (response.status !== 200) {
                    console.log(`Failed to fetch data for query '${query}': HTTP ${response.status}`);
                    continue;
                }
                
                const data = response.data;
                
                // Check if there are items in the response
                if (data.items && data.items.length > 0) {
                    const items = data.items;
                    console.log(`Found ${items.length} items for query '${query}'`);
                    
                    for (const item of items) {
                        // Filter for products that actually have discounts/special pricing
                        const hasDiscount = this.checkIfSpecialProduct(item);
                        
                        // Only include products that have actual discounts or special pricing
                        if (hasDiscount) {
                            const product = this.parseSpecialProduct(item, query);
                            if (product) {
                                products.push(product);
                                specialProductCount++;
                                
                                // Stop if we've reached the target
                                if (specialProductCount >= targetProducts) {
                                    break;
                                }
                            }
                        }
                    }
                    
                    const queryProducts = products.filter(p => p.searchQuery === query);
                    console.log(`Added ${queryProducts.length} special products from '${query}' search`);
                } else {
                    console.log(`No items found for query '${query}'`);
                }
                
                // Respectful delay between searches
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            // Remove duplicates based on SKU
            const uniqueProducts = this.removeDuplicates(products);
            
            // Ensure we don't exceed target
            const finalProducts = uniqueProducts.slice(0, targetProducts);
            
            console.log(`Successfully fetched ${finalProducts.length} special products from IGA`);
            return this.sortProductsByPrice(finalProducts);
            
        } catch (error) {
            console.error('Error fetching special products:', error.message);
            throw error;
        }
    }

    // Check if a product has discount or special pricing
    checkIfSpecialProduct(item) {
        try {
            const originalPrice = item.wasPriceNumeric || 0;
            const currentPrice = item.priceNumeric || 0;
            const priceLabel = (item.priceLabel || '').toLowerCase();
            
            // Check if this is actually a special/discounted product
            const hasNumericDiscount = originalPrice && currentPrice && originalPrice > currentPrice;
            const hasSpecialTerms = ['special', 'half', 'price', 'off', 'save', 'deal', 'discount']
                .some(term => priceLabel.includes(term));
            
            return hasNumericDiscount || hasSpecialTerms;
        } catch (error) {
            return false;
        }
    }

    // Parse product with special product information
    parseSpecialProduct(item, searchQuery) {
        try {
            const product = {};
            
            // Basic product info
            product.title = item.name || 'Unknown';
            product.store = 'IGA';
            
            // Handle price using IGA API structure
            product.price = item.price || 'N/A';
            product.priceNumeric = item.priceNumeric || 0;
            product.originalPrice = item.wasPrice || null;
            product.originalPriceNumeric = item.wasPriceNumeric || null;
            product.discountedPrice = item.price || 'N/A';
            
            // Set discount fields for compatibility
            if (item.wasPrice) {
                product.discount = item.wasPrice;
            } else {
                product.discount = null;
            }
            
            // Extract numeric price for sorting
            product.numericPrice = this.parsePrice(item.price);
            
            // Handle image URL - IGA API structure
            let imageUrl = null;
            const imageData = item.image || {};
            if (typeof imageData === 'object') {
                imageUrl = imageData.default;
            } else {
                imageUrl = imageData;
            }
            product.imageUrl = imageUrl;
            
            // Basic metadata
            product.brand = item.brand || 'IGA';
            product.unitPrice = item.pricePerUnit || 'N/A';
            product.productType = 'special';  // Mark as special product
            product.promotionId = item.productId || item.sku || 'N/A';
            product.sku = item.sku || 'N/A';
            product.inStock = true;
            product.category = '';
            
            // Additional special product fields from IGA API
            product.promotionText = item.priceLabel || '';
            product.description = item.description || '';
            product.sellBy = item.sellBy || '';
            product.unitOfSize = item.unitOfSize || {};
            product.available = item.available !== undefined ? item.available : true;
            product.searchQuery = searchQuery;  // Track which query found this product
            
            // Calculate savings if possible
            if (product.originalPriceNumeric && product.priceNumeric && 
                product.originalPriceNumeric > product.priceNumeric) {
                product.savingsAmount = product.originalPriceNumeric - product.priceNumeric;
                product.savingsPercentage = Math.round(
                    ((product.originalPriceNumeric - product.priceNumeric) / product.originalPriceNumeric) * 100 * 10
                ) / 10;
            }
            
            // TPR (Temporary Price Reduction) information
            const tprInfo = item.tprPrice || [];
            if (tprInfo && tprInfo.length > 0) {
                const tpr = tprInfo[0];
                product.markdownAmount = tpr.markdown || 0;
                product.tprLabel = tpr.label || '';
                product.tprActive = tpr.active || false;
            }
            
            // Promotion information
            const promotions = item.promotions || [];
            product.promotionsCount = item.totalNumberOfPromotions || 0;
            if (promotions.length > 0) {
                product.promotionDetails = promotions.map(p => p.name || '');
            }
            
            // Product URL
            product.productUrl = this.buildProductUrl(item);
            
            return product;
        } catch (error) {
            console.error('Error parsing special product:', error);
            return null;
        }
    }

    // Remove duplicates based on SKU
    removeDuplicates(products) {
        const seenSkus = new Set();
        const uniqueProducts = [];
        
        for (const product of products) {
            const sku = product.sku || product.promotionId || '';
            if (!seenSkus.has(sku)) {
                seenSkus.add(sku);
                uniqueProducts.push(product);
            }
        }
        
        return uniqueProducts;
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

    // Static method for fetching special products
    static async fetchSpecial(targetProducts = 500, limitPerPage = 100, storeId = null) {
        const scraper = new IGAScraper();
        await scraper.init();
        const results = await scraper.fetchSpecialProducts(limitPerPage, targetProducts, storeId);
        await scraper.close();
        
        console.log(`Fetched ${results.length} special products`);
        
        if (results.length > 0) {
            results.forEach((product, index) => {
                console.log("--->>>");
                console.log(`Special Product ${index + 1}:`);
                console.log(`Name: ${product.title}`);
                console.log(`Price: ${product.price} ($${product.priceNumeric.toFixed(2)})`);
                console.log(`Original Price: ${product.originalPrice || 'N/A'}`);
                if (product.markdownAmount) {
                    console.log(`Savings: $${product.markdownAmount.toFixed(2)}`);
                }
                console.log(`Promotion Text: ${product.promotionText}`);
                console.log(`TPR Label: ${product.tprLabel || 'N/A'}`);
                console.log(`Image URL: ${product.imageUrl}`);
                console.log(`Brand: ${product.brand}`);
                console.log(`Store: ${product.store}`);
                console.log(`Unit Price: ${product.unitPrice}`);
                console.log(`SKU: ${product.sku}`);
                console.log(`Available: ${product.available}`);
                console.log(`Promotions Count: ${product.promotionsCount}`);
                console.log("---");
            });
        } else {
            console.log("No special products found.");
        }
        
        return results;
    }
}

module.exports = IGAScraper;

// Command line usage
if (require.main === module) {
    const firstArg = process.argv[2];
    
    if (!firstArg) {
        console.log("Usage:");
        console.log("  node iga.js <search_query>     - Search for specific products");
        console.log("  node iga.js special [count]    - Fetch special products");
        console.log("");
        console.log("Examples:");
        console.log("  node iga.js 'milk'");
        console.log("  node iga.js special");
        console.log("  node iga.js special 200");
        process.exit(1);
    }
    
    if (firstArg.toLowerCase() === 'special') {
        // Special products mode
        let targetCount = 500;
        if (process.argv[3]) {
            const parsedCount = parseInt(process.argv[3]);
            if (!isNaN(parsedCount)) {
                targetCount = parsedCount;
            } else {
                console.log("Invalid target count, using default 500");
            }
        }
        
        console.log(`Fetching ${targetCount} IGA special products...`);
        IGAScraper.fetchSpecial(targetCount)
            .then(results => {
                if (results.length === 0) {
                    console.log("No special products found.");
                }
            })
            .catch(error => {
                console.error('Error:', error.message);
                process.exit(1);
            });
    } else {
        // Regular search mode
        const query = firstArg;
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
}
