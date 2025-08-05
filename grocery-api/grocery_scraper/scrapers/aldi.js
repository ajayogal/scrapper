const axios = require('axios');

class AldiScraper {
    constructor() {
        this.baseUrl = 'https://api.aldi.com.au/v3/product-search';
        this.defaultServicePoint = 'G452';
    }

    async init() {
        // No initialization needed for API-based scraper
        return Promise.resolve();
    }

    async searchProducts(query, maxResults = 50, servicePoint = null) {
        try {
            const limit = 30; // API limit per request
            let offset = 0;
            const products = [];
            const actualServicePoint = servicePoint || this.defaultServicePoint;

            while (products.length < maxResults) {
                const params = {
                    currency: 'AUD',
                    serviceType: 'walk-in',
                    q: query,
                    limit: limit,
                    offset: offset,
                    sort: 'relevance',
                    testVariant: 'A',
                    servicePoint: actualServicePoint
                };

                const response = await axios.get(this.baseUrl, { params });
                
                if (response.status !== 200) {
                    console.error(`Failed to fetch data: HTTP ${response.status}`);
                    break;
                }

                const data = response.data;
                if (!data.data || data.data.length === 0) {
                    break;
                }
                
                // Debug: Log first item to see discount structure
                if (offset === 0 && data.data.length > 0) {
                    console.log('Debug - First API item:', JSON.stringify(data.data[0], null, 2));
                }

                for (const item of data.data) {
                    if (products.length >= maxResults) break;

                    const product = this.parseProduct(item);
                    if (product) {
                        products.push(product);
                    }
                }

                // Check pagination
                const pagination = data.meta?.pagination;
                const total = pagination?.totalCount || 0;
                offset += limit;
                
                if (offset >= total) {
                    break;
                }

                // Respectful delay to avoid hammering the API
                await new Promise(resolve => setTimeout(resolve, 1000));
            }

            return this.sortProductsByPrice(products);

        } catch (error) {
            console.error('Error searching Aldi products:', error.message);
            throw error;
        }
    }

    parseProduct(item) {
        try {
            const product = {};
            
            // Basic product info matching expected format
            product.title = item.name || 'Unknown Product';
            product.store = 'Aldi';
            
            // Price information
            const priceObj = item.price || {};
            const currentPrice = priceObj.amountRelevantDisplay || null;
            const wasPrice = priceObj.wasPriceDisplay || null;
            
            // Set price fields according to expected format
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
            
            // Image handling
            product.imageUrl = this.getProductImage(item);
            
            // Additional metadata matching expected format
            product.productUrl = this.buildProductUrl(item);
            product.inStock = true; // Assume available if returned by API
            product.unitPrice = ''; // Aldi API doesn't provide unit pricing
            product.brand = this.extractBrand(item.name);
            product.category = ''; // Aldi API doesn't provide category info
            
            return product;
        } catch (error) {
            console.error('Error parsing product:', error);
            return null;
        }
    }

    getProductImage(item) {
        try {
            const assets = item.assets || [];
            let imageUrl = null;
            
            // Look for 'FR01' type first (preferred)
            for (const asset of assets) {
                if (asset.assetType === 'FR01') {
                    imageUrl = asset.url;
                    break;
                }
            }
            
            // Fallback to first available image
            if (!imageUrl && assets.length > 0) {
                imageUrl = assets[0].url;
            }
            
            // Fill width/slug placeholders for image URL
            if (imageUrl) {
                const slug = item.urlSlugText || '';
                imageUrl = imageUrl.replace('{width}', '300').replace('{slug}', slug);
            }
            
            return imageUrl;
        } catch (error) {
            console.error('Error getting product image:', error);
            return null;
        }
    }

    buildProductUrl(item) {
        try {
            const slug = item.urlSlugText;
            if (slug) {
                return `https://www.aldi.com.au/groceries/product-detail/ps/${slug}/`;
            }
            return null;
        } catch (error) {
            return null;
        }
    }

    parsePrice(priceStr) {
        try {
            if (!priceStr) return Infinity;
            // Remove currency symbol and convert to float
            const numericPrice = priceStr.replace(/[$,]/g, '');
            return parseFloat(numericPrice) || Infinity;
        } catch (error) {
            return Infinity;
        }
    }

    extractBrand(productName) {
        try {
            if (!productName) return '';
            // For Aldi, most products don't have explicit brands in the name
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
            
            return ''; // Most Aldi products are store brand
        } catch (error) {
            return '';
        }
    }

    sortProductsByPrice(products) {
        return products.sort((a, b) => a.numericPrice - b.numericPrice);
    }

    async close() {
        // No cleanup needed for API-based scraper
        return Promise.resolve();
    }

    // Utility method to get products with discount information
    async getDiscountedProducts(query, maxResults = 50, servicePoint = null) {
        const products = await this.searchProducts(query, maxResults, servicePoint);
        return products.filter(product => product.discountPrice);
    }

    // Method to search by specific service point (store location)
    async searchByLocation(query, servicePoint, maxResults = 50) {
        return this.searchProducts(query, maxResults, servicePoint);
    }
}

module.exports = AldiScraper;