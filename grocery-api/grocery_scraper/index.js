const WoolworthsScraper = require('./scrapers/woolworths');
const ColesScraper = require('./scrapers/coles');
const IGAScraper = require('./scrapers/iga');
const HarrisScraper = require('./scrapers/harris');

class GroceryScraper {
    constructor() {
        this.scrapers = {
            woolworths: new WoolworthsScraper(),
            coles: new ColesScraper(),
            iga: new IGAScraper(),
            harris: new HarrisScraper()
        };
    }

    async scrapeStore(storeName, query, maxResults = 20) {
        const scraper = this.scrapers[storeName.toLowerCase()];
        if (!scraper) {
            throw new Error(`Store "${storeName}" not supported. Available stores: ${Object.keys(this.scrapers).join(', ')}`);
        }

        console.log(`Scraping ${storeName} for "${query}"...`);
        const products = await scraper.searchProducts(query, maxResults);
        console.log(`Found ${products.length} products from ${storeName}`);
        
        return products;
    }

    async scrapeAllStores(query, maxResults = 50) {
        console.log(`Scraping all stores for "${query}"...`);
        const results = {};
        const promises = [];

        for (const [storeName, scraper] of Object.entries(this.scrapers)) {
            promises.push(
                this.scrapeStore(storeName, query, maxResults)
                    .then(products => {
                        results[storeName] = products;
                    })
                    .catch(error => {
                        console.error(`Error scraping ${storeName}:`, error.message);
                        results[storeName] = [];
                    })
            );
        }

        await Promise.all(promises);
        
        const totalProducts = Object.values(results).reduce((sum, products) => sum + products.length, 0);
        console.log(`Total products found across all stores: ${totalProducts}`);
        
        return results;
    }

    async getProductDetails(storeName, productUrl) {
        const scraper = this.scrapers[storeName.toLowerCase()];
        if (!scraper) {
            throw new Error(`Store "${storeName}" not supported`);
        }

        return await scraper.getProductDetails(productUrl);
    }

    async closeAll() {
        console.log('Closing all scrapers...');
        const promises = Object.values(this.scrapers).map(scraper => scraper.close());
        await Promise.all(promises);
        console.log('All scrapers closed');
    }

    // Utility method to get all products in a flat array
    flattenResults(results) {
        const allProducts = [];
        for (const [store, products] of Object.entries(results)) {
            allProducts.push(...products);
        }
        return allProducts;
    }

    // Utility method to sort products by price (cheapest first by default)
    sortByPrice(products, ascending = true) {
        return products.sort((a, b) => {
            const priceA = a.numericPrice || parseFloat(a.price.replace(/[^0-9.]/g, '')) || 0;
            const priceB = b.numericPrice || parseFloat(b.price.replace(/[^0-9.]/g, '')) || 0;
            return ascending ? priceA - priceB : priceB - priceA;
        });
    }

    // Utility method to filter products by stock status
    filterInStock(products) {
        return products.filter(product => product.inStock);
    }

    // Utility method to filter products with discounts
    filterDiscounted(products) {
        return products.filter(product => product.discount && product.discount.length > 0);
    }

    // Utility method to filter products by store
    filterByStore(products, storeName) {
        return products.filter(product => 
            product.store.toLowerCase().includes(storeName.toLowerCase())
        );
    }

    // Utility method to search within results
    searchInResults(products, searchTerm) {
        const term = searchTerm.toLowerCase();
        return products.filter(product =>
            product.name.toLowerCase().includes(term) ||
            product.store.toLowerCase().includes(term)
        );
    }
}

// Command line interface
async function main() {
    const args = process.argv.slice(2);
    
    if (args.length === 0) {
        console.log(`
Usage: node index.js <command> [options]

Commands:
  search <query> [store] [maxResults]  - Search for products
  help                                 - Show this help message

Examples:
  node index.js search milk                    - Search all stores for milk
  node index.js search bread woolworths        - Search Woolworths for bread
  node index.js search coffee coles 20        - Search Coles for coffee (max 20 results)
  node index.js search "organic eggs" harris   - Search Harris Farm for organic eggs

Supported stores: woolworths, coles, iga, harris
        `);
        return;
    }

    const command = args[0];
    const scraper = new GroceryScraper();

    try {
        switch (command) {
            case 'search':
                if (args.length < 2) {
                    console.error('Please provide a search query');
                    return;
                }

                const query = args[1];
                const store = args[2];
                const maxResults = parseInt(args[3]) || 50;
                
                // Check if JSON output is requested (for API usage)
                const outputJson = args.includes('--json');

                let results;
                if (store && Object.keys(scraper.scrapers).includes(store.toLowerCase())) {
                    results = await scraper.scrapeStore(store, query, maxResults);
                    
                    if (outputJson) {
                        // Output JSON for API consumption
                        console.log(JSON.stringify({
                            success: true,
                            query: query,
                            store: store,
                            products: results,
                            totalResults: results.length
                        }));
                    } else {
                        // Human-readable output for CLI
                        console.log('\n=== RESULTS ===');
                        results.forEach((product, index) => {
                            console.log(`${index + 1}. ${product.title}`);
                            console.log(`   Store: ${product.store}`);
                            console.log(`   Price: ${product.price}`);
                            if (product.discount) console.log(`   Discount: ${product.discount}`);
                            if (product.discountedPrice) console.log(`   Discounted Price: ${product.discountedPrice}`);
                            if (product.unitPrice) console.log(`   Unit Price: ${product.unitPrice}`);
                            console.log(`   In Stock: ${product.inStock ? 'Yes' : 'No'}`);
                            if (product.brand) console.log(`   Brand: ${product.brand}`);
                            if (product.category) console.log(`   Category: ${product.category}`);
                            console.log(`   URL: ${product.productUrl}`);
                            console.log('');
                        });
                    }
                } else {
                    results = await scraper.scrapeAllStores(query, maxResults);
                    
                    if (outputJson) {
                        // Flatten all products for JSON output
                        const allProducts = scraper.flattenResults(results);
                        const sortedProducts = scraper.sortByPrice(allProducts);
                        
                        console.log(JSON.stringify({
                            success: true,
                            query: query,
                            store: 'all',
                            products: sortedProducts,
                            totalResults: sortedProducts.length,
                            storeResults: results
                        }));
                    } else {
                        // Human-readable output for CLI
                        console.log('\n=== RESULTS BY STORE ===');
                        
                        for (const [storeName, products] of Object.entries(results)) {
                            console.log(`\n--- ${storeName.toUpperCase()} (${products.length} products) ---`);
                            products.forEach((product, index) => {
                                console.log(`${index + 1}. ${product.title}`);
                                console.log(`   Price: ${product.price}`);
                                if (product.discount) console.log(`   Discount: ${product.discount}`);
                                if (product.discountedPrice) console.log(`   Discounted Price: ${product.discountedPrice}`);
                                if (product.unitPrice) console.log(`   Unit Price: ${product.unitPrice}`);
                                console.log(`   In Stock: ${product.inStock ? 'Yes' : 'No'}`);
                                if (product.brand) console.log(`   Brand: ${product.brand}`);
                                console.log('');
                            });
                        }

                        // Show combined results sorted by price
                        const allProducts = scraper.flattenResults(results);
                        const sortedProducts = scraper.sortByPrice(allProducts);
                        
                        console.log('\n=== ALL RESULTS SORTED BY PRICE (CHEAPEST FIRST) ===');
                        sortedProducts.forEach((product, index) => {
                            console.log(`${index + 1}. ${product.title} - ${product.store}`);
                            console.log(`   Price: ${product.price}`);
                            if (product.discount) console.log(`   Discount: ${product.discount}`);
                            if (product.discountedPrice) console.log(`   Discounted Price: ${product.discountedPrice}`);
                            if (product.unitPrice) console.log(`   Unit Price: ${product.unitPrice}`);
                            console.log(`   In Stock: ${product.inStock ? 'Yes' : 'No'}`);
                            if (product.brand) console.log(`   Brand: ${product.brand}`);
                            console.log('');
                        });
                    }
                }
                break;

            case 'help':
                console.log(`
Grocery Scraper - Node.js Web Scraping Tool

This tool scrapes product information from major Australian grocery stores:
- Woolworths (woolworths.com.au)
- Coles (coles.com.au) 
- IGA (igashop.com.au)
- Harris Farm Markets (harrisfarm.com.au)

Usage: node index.js <command> [options]

Commands:
  search <query> [store] [maxResults]  - Search for products
  help                                 - Show this help message

Examples:
  node index.js search milk                    - Search all stores for milk
  node index.js search bread woolworths        - Search Woolworths for bread
  node index.js search coffee coles 20        - Search Coles for coffee (max 20 results)
  node index.js search "organic eggs" harris   - Search Harris Farm for organic eggs

Features:
- Concurrent scraping of multiple stores
- Price comparison across stores
- Product details extraction
- Flexible search options
- Error handling and retry logic

Note: This tool is for educational purposes. Please respect the websites' terms of service and robots.txt files.
                `);
                break;

            default:
                console.error(`Unknown command: ${command}`);
                console.log('Use "node index.js help" for usage information');
        }
    } catch (error) {
        console.error('Error:', error.message);
    } finally {
        await scraper.closeAll();
    }
}

// Export for use as a module
module.exports = GroceryScraper;

// Run CLI if this file is executed directly
if (require.main === module) {
    main().catch(console.error);
}

