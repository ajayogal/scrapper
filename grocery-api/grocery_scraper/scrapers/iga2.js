const puppeteer = require('puppeteer');
const fs = require('fs').promises;

class IGAScraper {
    constructor(headless = true) {
        this.browser = null;
        this.page = null;
        this.baseUrl = "https://www.igashop.com.au";
        this.headless = headless;
    }

    async init() {
        this.browser = await puppeteer.launch({
            headless: this.headless,
            args: [
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--window-size=1920,1080'
            ]
        });
        this.page = await this.browser.newPage();
        
        // Set user agent to avoid detection
        await this.page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36');
        
        // Set viewport
        await this.page.setViewport({ width: 1920, height: 1080 });
    }

    /**
     * Search for products on IGA website with backward compatibility
     * Can be called as:
     * 1. searchProducts(query, maxResults) - for compatibility with index.js
     * 2. searchProducts(query, options) - for advanced features
     * @param {string} query - Search term
     * @param {number|object} maxPagesOrOptions - Either maxResults (number) or options object
     * @param {boolean} interactive - Ask user before loading each new page (when using old interface)
     * @param {number} specificPage - Scrape only a specific page number (when using old interface)
     * @returns {Array} List of product objects
     */
    async searchProducts(query, maxPagesOrOptions = 1, interactive = false, specificPage = null) {
        // Handle backward compatibility with original interface
        let maxPages = 1;
        let maxResults = null;
        
        if (typeof maxPagesOrOptions === 'number') {
            // Check if this looks like a maxResults call (large number) vs maxPages call (small number)
            if (maxPagesOrOptions > 2) {
                // Assume this is maxResults from index.js
                maxResults = maxPagesOrOptions;
                maxPages = 2; // Set high limit, but will stop when maxResults is reached
                // Debug: console.log(`Detected maxResults mode: target ${maxResults} products`);
            } else {
                // Assume this is maxPages from CLI
                maxPages = maxPagesOrOptions;
                // Debug: console.log(`Detected maxPages mode: target ${maxPages} pages`);
            }
        } else if (typeof maxPagesOrOptions === 'object') {
            // New options object interface
            const options = maxPagesOrOptions;
            maxPages = options.maxPages || 1;
            interactive = options.interactive || false;
            specificPage = options.specificPage || null;
            maxResults = options.maxResults || null;
        }
        try {
            if (!this.browser) {
                await this.init();
            }

            let products = [];
            
            // If specific page is requested, scrape only that page
            if (specificPage) {
                const searchUrl = `${this.baseUrl}/search/${specificPage}?q=${encodeURIComponent(query)}`;
                console.log(`Scraping page ${specificPage}: ${searchUrl}`);
                
                await this.page.goto(searchUrl, { waitUntil: 'networkidle2', timeout: 60000 });
                await this._waitForPageLoad();
                
                const pageProducts = await this._parseProducts();
                if (pageProducts.length > 0) {
                    products.push(...pageProducts);
                    console.log(`Found ${pageProducts.length} products on page ${specificPage}`);
                } else {
                    console.log(`No products found on page ${specificPage}`);
                }
                
                // Apply maxResults limit if specified
                if (maxResults && products.length > maxResults) {
                    products = products.slice(0, maxResults);
                }
                
                return products;
            }

            // Regular multi-page scraping
            let page = 1;
            
            // Debug output (commented for API compatibility)
            // if (maxResults) {
            //     console.log(`Target: ${maxResults} products (will stop when reached)`);
            // } else {
            //     console.log(`Target: ${maxPages} pages`);
            // }
            
            while (true) {
                // Check if we should stop based on maxPages limit
                if (maxPages > 0 && maxPages !== 999 && page > maxPages) {
                    // Debug: console.log(`Reached page limit (${maxPages}), stopping.`);
                    break;
                }
                
                // Check if we have enough results BEFORE scraping next page
                if (maxResults && products.length >= maxResults) {
                    // Debug: console.log(`Reached target of ${maxResults} products (${products.length}), stopping.`);
                    break;
                }
                
                const searchUrl = `${this.baseUrl}/search/${page}?q=${encodeURIComponent(query)}`;
                // Only log if not being called from API (avoid JSON parsing issues)
                if (!process.argv.includes('--json')) {
                    console.log(`Scraping page ${page}: ${searchUrl} (current: ${products.length} products)`);
                }
                
                await this.page.goto(searchUrl, { waitUntil: 'networkidle2', timeout: 60000 });
                await this._waitForPageLoad();
                
                const pageProducts = await this._parseProducts();
                
                if (pageProducts.length === 0) {
                    if (!process.argv.includes('--json')) {
                        console.log(`No products found on page ${page}`);
                    }
                    break;
                }
                
                products.push(...pageProducts);
                if (!process.argv.includes('--json')) {
                    console.log(`Found ${pageProducts.length} products on page ${page} (total: ${products.length})`);
                }
                
                // Check again after adding products from this page
                if (maxResults && products.length >= maxResults) {
                    // Debug: console.log(`Target reached after page ${page}, stopping.`);
                    break;
                }
                
                // Interactive mode: ask user if they want to continue
                if (interactive && (maxPages === 0 || page < maxPages) && (!maxResults || products.length < maxResults)) {
                    console.log(`\nCurrent total: ${products.length} products`);
                    
                    // In Node.js, we can use readline for interactive input
                    const readline = require('readline');
                    const rl = readline.createInterface({
                        input: process.stdin,
                        output: process.stdout
                    });
                    
                    const userInput = await new Promise(resolve => {
                        rl.question('Continue to next page? (y/n/show): ', resolve);
                    });
                    
                    if (userInput.toLowerCase().trim() === 'show') {
                        console.log(`\n=== Current Results (${products.length} products) ===`);
                        products.forEach((product, i) => {
                            const discountText = product.discount !== "N/A" ? ` (save ${product.discount})` : "";
                            console.log(`${i + 1}. ${product.name} - ${product.price} (${product.quantity})${discountText}`);
                        });
                        console.log("=".repeat(50));
                        
                        const continueInput = await new Promise(resolve => {
                            rl.question('Continue to next page? (y/n): ', resolve);
                        });
                        
                        if (!['y', 'yes'].includes(continueInput.toLowerCase().trim())) {
                            console.log("Stopping pagination as requested.");
                            rl.close();
                            break;
                        }
                    } else if (!['y', 'yes'].includes(userInput.toLowerCase().trim())) {
                        console.log("Stopping pagination as requested.");
                        rl.close();
                        break;
                    }
                    
                    rl.close();
                }
                
                page++;
            }
            
            // Apply maxResults limit if specified
            if (maxResults && products.length > maxResults) {
                products = products.slice(0, maxResults);
            }
            
            if (!process.argv.includes('--json')) {
                console.log(`Found ${products.length} total products from IGA`);
            }
            return products;

        } catch (error) {
            console.error('IGA scraping error:', error);
            return [];
        }
    }

    /**
     * Wait for page to load and handle popups
     */
    async _waitForPageLoad() {
        // Wait for page to load
        await new Promise(resolve => setTimeout(resolve, 10000));
        
        // Handle the location popup by clicking "Browse as a guest"
        try {
            const guestButton = await this.page.$x("//button[contains(text(), 'Browse as a guest')]");
            if (guestButton.length > 0) {
                await guestButton[0].click();
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        } catch (e) {
            console.log('No location popup found or already handled');
        }
    }

    /**
     * Parse products from the current page using improved logic from Python version
     */
    async _parseProducts() {
        return await this.page.evaluate((baseUrl) => {
            const products = [];
            
            // Find all elements with href="/product/..." containing product information
            const productLinks = Array.from(document.querySelectorAll('a[href*="/product/"]'));
            
            for (const productLink of productLinks) {
                try {
                    // Extract name from image alt text
                    const imageElement = productLink.querySelector('img');
                    const name = imageElement ? (imageElement.alt || "N/A") : "N/A";
                    
                    // Get image URL
                    let imageUrl = imageElement ? (imageElement.src || "N/A") : "N/A";
                    
                    // Find the parent container that might contain price information
                    const parent = productLink.parentElement;
                    let price = "N/A";
                    let quantity = "N/A";
                    let discount = "N/A";
                    
                    // Look for price in parent or nearby elements
                    const searchContainers = [
                        parent,
                        parent ? parent.parentElement : null,
                        productLink.nextElementSibling
                    ].filter(c => c !== null);
                    
                    for (const container of searchContainers) {
                        // Get ALL text from the container
                        const containerText = container.textContent || '';
                        
                        // Check for special badge first
                        const specialBadge = container.querySelector('[data-badge="special"]');
                        const hasSpecial = specialBadge !== null;
                        
                        // Try to find price in the container text
                        if (containerText.includes('$')) {
                            // Extract quantity/size information
                            const quantityPatterns = [
                                /(\d+(?:\.\d+)?\s*(?:Litre|Liter|L))/i,
                                /(\d+(?:\.\d+)?\s*(?:Millilitre|Milliliter|mL|ML))/i,
                                /(\d+(?:\.\d+)?\s*(?:Gram|g|G))/i,
                                /(\d+(?:\.\d+)?\s*(?:Kilogram|kg|KG))/i,
                                /(\d+(?:\.\d+)?\s*(?:Pack|pk))/i,
                                /(\d+(?:\.\d+)?\s*(?:Each|ea))/i,
                            ];
                            
                            for (const pattern of quantityPatterns) {
                                const quantityMatch = containerText.match(pattern);
                                if (quantityMatch) {
                                    quantity = quantityMatch[1].trim();
                                    break;
                                }
                            }
                            
                            // Extract all prices from the text
                            const priceMatches = containerText.match(/\$\d+\.\d+/g);
                            if (priceMatches) {
                                // Handle special pricing logic
                                if (hasSpecial && priceMatches.length >= 2) {
                                    // With special badge: usually "was $X.XX now $Y.YY"
                                    const price1 = parseFloat(priceMatches[0].replace('$', ''));
                                    const price2 = parseFloat(priceMatches[1].replace('$', ''));
                                    
                                    if (price2 < price1) {
                                        price = priceMatches[1];
                                        const savings = price1 - price2;
                                        discount = `$${savings.toFixed(2)}`;
                                    } else {
                                        price = priceMatches[0];
                                        const savings = price2 - price1;
                                        discount = `$${savings.toFixed(2)}`;
                                    }
                                } else if (hasSpecial) {
                                    price = priceMatches[0];
                                    discount = "Special price";
                                } else if (priceMatches.length >= 2) {
                                    // Multiple prices without special badge
                                    const containerLower = containerText.toLowerCase();
                                    if (['was', 'now', 'special', 'save'].some(word => containerLower.includes(word))) {
                                        price = priceMatches[1];
                                        const price1 = parseFloat(priceMatches[0].replace('$', ''));
                                        const price2 = parseFloat(priceMatches[1].replace('$', ''));
                                        const savings = price1 - price2;
                                        discount = `$${savings.toFixed(2)}`;
                                    } else {
                                        price = priceMatches[0];
                                    }
                                } else {
                                    price = priceMatches[0];
                                }
                                break;
                            }
                        }
                    }
                    
                    // Clean up image URL if it's relative
                    if (imageUrl && !imageUrl.startsWith("http")) {
                        if (imageUrl.startsWith("//")) {
                            imageUrl = "https:" + imageUrl;
                        } else if (imageUrl !== "N/A") {
                            imageUrl = baseUrl + imageUrl;
                        }
                    }
                    
                    // Only add product if a name is found
                    if (name !== "N/A") {
                        // Calculate numeric price for sorting (inline function for page.evaluate context)
                        let numericPrice = 0;
                        if (price !== "N/A" && price) {
                            const numbers = price.match(/\d+\.?\d*/g);
                            if (numbers && numbers.length > 0) {
                                numericPrice = parseFloat(numbers[0]);
                            }
                        }
                        
                        // Extract brand from name (inline function for page.evaluate context)
                        let brand = "Unknown";
                        if (name && name !== "N/A") {
                            const words = name.split(' ');
                            brand = words.length > 0 ? words[0] : "Unknown";
                        }
                        
                        products.push({
                            title: name,  // Use 'title' to match other scrapers
                            name: name,   // Keep 'name' for backward compatibility with CLI
                            price: price,
                            quantity: quantity,
                            imageUrl: imageUrl,
                            discount: discount !== "N/A" ? discount : "",
                            discountedPrice: discount !== "N/A" && price !== "N/A" ? price : "",
                            numericPrice: numericPrice,
                            inStock: true, // Assume in stock if found
                            unitPrice: "",  // Could be enhanced later
                            productUrl: "", // Could be enhanced later
                            brand: brand,
                            category: "Grocery",
                            store: 'IGA',
                            scraped_at: new Date().toISOString()
                        });
                    }
                } catch (error) {
                    console.error('Error extracting product data:', error);
                }
            }
            
            // Remove duplicates based on name
            const seen = new Set();
            const uniqueProducts = products.filter(product => {
                if (seen.has(product.name)) {
                    return false;
                }
                seen.add(product.name);
                return true;
            });
            
            return uniqueProducts;
        }, this.baseUrl);
    }

    /**
     * Sort products by price or discount
     * @param {Array} products - List of product objects
     * @param {string} sortBy - "price" or "discount"
     * @param {boolean} reverse - True for descending order
     * @returns {Array} Sorted list of products
     */
    sortProducts(products, sortBy = "price", reverse = false) {
        if (sortBy === "price") {
            const sorted = products.sort((a, b) => {
                const priceA = this._extractPriceValue(a.price);
                const priceB = this._extractPriceValue(b.price);
                return priceA - priceB;
            });
            return reverse ? sorted.reverse() : sorted;
        } else if (sortBy === "discount") {
            // Sort by discount availability (discounted items first)
            const sorted = products.sort((a, b) => {
                const hasDiscountA = a.discount !== "N/A";
                const hasDiscountB = b.discount !== "N/A";
                return hasDiscountB - hasDiscountA;
            });
            return sorted;
        } else {
            return products;
        }
    }

    /**
     * Extract numeric value from price string
     * @param {string} priceStr - Price string like "$5.99"
     * @returns {number} Numeric price value
     */
    _extractPriceValue(priceStr) {
        if (priceStr === "N/A") {
            return Infinity;
        }
        
        // Extract numbers from price string
        const numbers = priceStr.match(/\d+\.?\d*/g);
        if (numbers && numbers.length > 0) {
            return parseFloat(numbers[0]);
        }
        return Infinity;
    }

    /**
     * Extract numeric value from price string (for use in page.evaluate)
     * @param {string} priceStr - Price string like "$5.99"
     * @returns {number} Numeric price value
     */
    _extractPriceValueFromString(priceStr) {
        if (priceStr === "N/A" || !priceStr) {
            return 0;
        }
        
        // Extract numbers from price string
        const numbers = priceStr.match(/\d+\.?\d*/g);
        if (numbers && numbers.length > 0) {
            return parseFloat(numbers[0]);
        }
        return 0;
    }

    /**
     * Extract brand from product name
     * @param {string} name - Product name
     * @returns {string} Extracted brand
     */
    _extractBrandFromName(name) {
        if (!name || name === "N/A") {
            return "Unknown";
        }
        
        // Extract first word as brand
        const words = name.split(' ');
        return words.length > 0 ? words[0] : "Unknown";
    }

    /**
     * Filter products that have discounts
     * @param {Array} products - List of product objects
     * @returns {Array} List of discounted products
     */
    getDiscountedProducts(products) {
        return products.filter(p => p.discount !== "N/A");
    }

    async scrapeSpecialProducts(maxResults = 50) {
        try {
            if (!this.browser) {
                await this.init();
            }

            let products = [];
            let page = 1;
            
            while (products.length < maxResults) {
                // Navigate to IGA special offers page
                const specialUrl = `https://www.igashop.com.au/specials/${page}`;
                if (!process.argv.includes('--json')) {
                    console.log(`Scraping IGA specials page ${page}: ${specialUrl} (current: ${products.length} products)`);
                }
                
                await this.page.goto(specialUrl, { waitUntil: 'networkidle2', timeout: 60000 });
                await this._waitForPageLoad();
                
                const pageProducts = await this._parseSpecialProducts();
                
                if (pageProducts.length === 0) {
                    if (!process.argv.includes('--json')) {
                        console.log(`No special products found on page ${page}`);
                    }
                    break;
                }
                
                products.push(...pageProducts);
                if (!process.argv.includes('--json')) {
                    console.log(`Found ${pageProducts.length} special products on page ${page} (total: ${products.length})`);
                }
                
                // Check if we have enough products
                if (products.length >= maxResults) {
                    break;
                }
                
                page++;
            }
            
            // Apply maxResults limit
            if (products.length > maxResults) {
                products = products.slice(0, maxResults);
            }
            
            if (!process.argv.includes('--json')) {
                console.log(`Found ${products.length} total special products from IGA`);
            }
            return products;

        } catch (error) {
            console.error('IGA special products scraping error:', error);
            return [];
        }
    }

    /**
     * Parse special products from the current page - similar to _parseProducts but focused on specials
     */
    async _parseSpecialProducts() {
        return await this.page.evaluate((baseUrl) => {
            const products = [];
            
            // Find all elements with href="/product/..." containing product information
            const productLinks = Array.from(document.querySelectorAll('a[href*="/product/"]'));
            
            for (const productLink of productLinks) {
                try {
                    // Extract name from image alt text
                    const imageElement = productLink.querySelector('img');
                    const name = imageElement ? (imageElement.alt || "N/A") : "N/A";
                    
                    // Get image URL
                    let imageUrl = imageElement ? (imageElement.src || "N/A") : "N/A";
                    
                    // Find the parent container that might contain price information
                    const parent = productLink.parentElement;
                    let price = "N/A";
                    let quantity = "N/A";
                    let discount = "N/A";
                    
                    // Look for price in parent or nearby elements
                    const searchContainers = [
                        parent,
                        parent ? parent.parentElement : null,
                        productLink.nextElementSibling
                    ].filter(c => c !== null);
                    
                    for (const container of searchContainers) {
                        // Get ALL text from the container
                        const containerText = container.textContent || '';
                        
                        // Check for special badge - prioritize products with special indicators
                        const specialBadge = container.querySelector('[data-badge="special"]');
                        const hasSpecial = specialBadge !== null;
                        
                        // Look for special indicators in text
                        const specialWords = ['special', 'save', 'was', 'now', 'off', '%'];
                        const hasSpecialText = specialWords.some(word => 
                            containerText.toLowerCase().includes(word)
                        );
                        
                        // Try to find price in the container text
                        if (containerText.includes('$')) {
                            // Extract quantity/size information
                            const quantityPatterns = [
                                /(\d+(?:\.\d+)?\s*(?:Litre|Liter|L))/i,
                                /(\d+(?:\.\d+)?\s*(?:Millilitre|Milliliter|mL|ML))/i,
                                /(\d+(?:\.\d+)?\s*(?:Gram|g|G))/i,
                                /(\d+(?:\.\d+)?\s*(?:Kilogram|kg|KG))/i,
                                /(\d+(?:\.\d+)?\s*(?:Pack|pk))/i,
                                /(\d+(?:\.\d+)?\s*(?:Each|ea))/i,
                            ];
                            
                            for (const pattern of quantityPatterns) {
                                const quantityMatch = containerText.match(pattern);
                                if (quantityMatch) {
                                    quantity = quantityMatch[1].trim();
                                    break;
                                }
                            }
                            
                            // Extract all prices from the text
                            const priceMatches = containerText.match(/\$\d+\.\d+/g);
                            if (priceMatches) {
                                // Handle special pricing logic
                                if ((hasSpecial || hasSpecialText) && priceMatches.length >= 2) {
                                    // With special badge/text: usually "was $X.XX now $Y.YY"
                                    const price1 = parseFloat(priceMatches[0].replace('$', ''));
                                    const price2 = parseFloat(priceMatches[1].replace('$', ''));
                                    
                                    if (price2 < price1) {
                                        price = priceMatches[1];
                                        const savings = price1 - price2;
                                        discount = `Save $${savings.toFixed(2)}`;
                                    } else {
                                        price = priceMatches[0];
                                        const savings = price2 - price1;
                                        discount = `Save $${savings.toFixed(2)}`;
                                    }
                                } else if (hasSpecial || hasSpecialText) {
                                    price = priceMatches[0];
                                    discount = "Special price";
                                } else if (priceMatches.length >= 2) {
                                    // Multiple prices - check for special keywords
                                    const containerLower = containerText.toLowerCase();
                                    if (['was', 'now', 'special', 'save'].some(word => containerLower.includes(word))) {
                                        price = priceMatches[1];
                                        const price1 = parseFloat(priceMatches[0].replace('$', ''));
                                        const price2 = parseFloat(priceMatches[1].replace('$', ''));
                                        const savings = Math.abs(price1 - price2);
                                        discount = `Save $${savings.toFixed(2)}`;
                                    } else {
                                        price = priceMatches[0];
                                        discount = "Special offer"; // Assume it's special since it's on specials page
                                    }
                                } else {
                                    price = priceMatches[0];
                                    discount = "Special offer"; // Assume it's special since it's on specials page
                                }
                                break;
                            }
                        }
                    }
                    
                    // Clean up image URL if it's relative
                    if (imageUrl && !imageUrl.startsWith("http")) {
                        if (imageUrl.startsWith("//")) {
                            imageUrl = "https:" + imageUrl;
                        } else if (imageUrl !== "N/A") {
                            imageUrl = baseUrl + imageUrl;
                        }
                    }
                    
                    // Only add product if a name is found and it has some special indicator
                    if (name !== "N/A" && discount !== "N/A") {
                        // Calculate numeric price for sorting
                        let numericPrice = 0;
                        if (price !== "N/A" && price) {
                            const numbers = price.match(/\d+\.?\d*/g);
                            if (numbers && numbers.length > 0) {
                                numericPrice = parseFloat(numbers[0]);
                            }
                        }
                        
                        // Extract brand from name
                        let brand = "Unknown";
                        if (name && name !== "N/A") {
                            const words = name.split(' ');
                            brand = words.length > 0 ? words[0] : "Unknown";
                        }
                        
                        products.push({
                            title: name,
                            name: name,
                            price: price,
                            quantity: quantity,
                            imageUrl: imageUrl,
                            discount: discount,
                            discountedPrice: discount !== "N/A" && price !== "N/A" ? price : "",
                            numericPrice: numericPrice,
                            inStock: true,
                            unitPrice: "",
                            productUrl: "",
                            brand: brand,
                            category: "Special Offers",
                            store: 'IGA',
                            scraped_at: new Date().toISOString()
                        });
                    }
                } catch (error) {
                    console.error('Error extracting special product data:', error);
                }
            }
            
            // Remove duplicates based on name
            const seen = new Set();
            const uniqueProducts = products.filter(product => {
                if (seen.has(product.name)) {
                    return false;
                }
                seen.add(product.name);
                return true;
            });
            
            return uniqueProducts;
        }, this.baseUrl);
    }

    /**
     * Save products to JSON file
     * @param {Array} products - List of product objects
     * @param {string} filename - Output filename
     */
    async saveToJson(products, filename) {
        try {
            await fs.writeFile(filename, JSON.stringify(products, null, 2), 'utf8');
            console.log(`Saved ${products.length} products to ${filename}`);
        } catch (error) {
            console.error(`Error saving to ${filename}:`, error);
        }
    }

    async close() {
        if (this.browser) {
            await this.browser.close();
            this.browser = null;
            this.page = null;
        }
    }
}

module.exports = IGAScraper;

