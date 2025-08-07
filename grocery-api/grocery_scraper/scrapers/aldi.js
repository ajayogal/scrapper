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
        return products.filter(product => product.discountedPrice);
    }

    // Method to search by specific service point (store location)
    async searchByLocation(query, servicePoint, maxResults = 50) {
        return this.searchProducts(query, maxResults, servicePoint);
    }

    // Fetch all categories from the category tree API
    async fetchCategories() {
        try {
            const categoriesUrl = 'https://api.aldi.com.au/v2/product-category-tree';
            const response = await axios.get(categoriesUrl);

            if (response.status !== 200) {
                console.error(`Failed to fetch categories: HTTP ${response.status}`);
                return [];
            }

            const data = response.data;
            return this.extractCategories(data.data || data);
        } catch (error) {
            console.error('Error fetching categories:', error.message);
            return [];
        }
    }

    // Extract category keys and names from the API response
    extractCategories(data) {
        const categoryKeys = [];
        
        for (const category of data) {
            const categoryKey = category.key;
            const categoryName = category.name;
            
            if (categoryKey) {
                categoryKeys.push({ key: categoryKey, name: categoryName });
            }
            
            console.log(`Category: ${categoryName}`);
        }
        
        return categoryKeys;
    }

    // Fetch special products from all categories
    async fetchSpecialProducts(servicePoint = null, limit = 16) {
        try {
            const actualServicePoint = servicePoint || this.defaultServicePoint;
            
            console.log('Fetching categories...');
            const categories = await this.fetchCategories();
            
            // Filter out unwanted categories
            const excludedCategories = ['Liquor', 'Cleaning & Household', 'Baby', 'Drinks', 'Pets'];
            const filteredCategories = categories.filter(cat => 
                !excludedCategories.includes(cat.name)
            );
            
            console.log(`Found ${categories.length} categories`);
            console.log(`Found ${filteredCategories.length} categories after filtering`);
            
            const allProducts = [];
            
            // Fetch products for each category
            for (const category of filteredCategories) {
                console.log(`Fetching products for category: ${category.name}`);
                
                const categoryProducts = await this.fetchProductsByCategory(
                    category.key, 
                    category.name, 
                    actualServicePoint, 
                    limit
                );
                
                allProducts.push(...categoryProducts);
                
                console.log(`  Found ${categoryProducts.length} products`);
                
                // Respectful delay between API calls
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            return this.sortProductsByPrice(allProducts);
        } catch (error) {
            console.error('Error fetching special products:', error.message);
            throw error;
        }
    }

    // Fetch products for a specific category
    async fetchProductsByCategory(categoryKey, categoryName, servicePoint, limit = 16) {
        try {
            const productsUrl = 'https://api.aldi.com.au/v3/product-search';
            const params = {
                currency: 'AUD',
                serviceType: 'walk-in',
                categoryKey: categoryKey,
                limit: limit,
                offset: 0,
                sort: 'price',
                testVariant: 'A',
                servicePoint: servicePoint
            };

            const response = await axios.get(productsUrl, { params });
            
            if (response.status !== 200) {
                console.error(`Failed to fetch products for category ${categoryName}: HTTP ${response.status}`);
                return [];
            }

            const data = response.data;
            const products = [];

            if (data.data && data.data.length > 0) {
                for (const item of data.data) {
                    const product = this.parseProductWithCategory(item, categoryKey, categoryName);
                    if (product) {
                        products.push(product);
                    }
                }
            }

            return products;
        } catch (error) {
            console.error(`Error fetching products for category ${categoryName}:`, error.message);
            return [];
        }
    }

    // Parse product with category information
    parseProductWithCategory(item, categoryKey, categoryName) {
        try {
            const product = this.parseProduct(item);
            if (product) {
                product.categoryKey = categoryKey;
                product.categoryName = categoryName;
            }
            return product;
        } catch (error) {
            console.error('Error parsing product with category:', error);
            return null;
        }
    }
}

module.exports = AldiScraper;