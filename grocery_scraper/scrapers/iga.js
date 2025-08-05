const puppeteer = require('puppeteer');

class IGAScraper {
    constructor() {
        this.browser = null;
        this.page = null;
    }

    async init() {
        this.browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        });
        this.page = await this.browser.newPage();
        
        // Set user agent to avoid detection
        await this.page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36');
        
        // Set viewport
        await this.page.setViewport({ width: 1280, height: 720 });
    }

    async searchProducts(query, maxResults = 20) {
        try {
            if (!this.browser) {
                await this.init();
            }

            const searchUrl = `https://www.igashop.com.au/search/1?q=${encodeURIComponent(query)}`;
            console.log(`Scraping IGA: ${searchUrl}`);

            await this.page.goto(searchUrl, { waitUntil: 'networkidle2', timeout: 60000 });

            // Handle the location popup by clicking "Browse as a guest"
            try {
                await this.page.waitForSelector('button:contains("Browse as a guest")', { timeout: 5000 });
                await this.page.click('button:contains("Browse as a guest")');
                await new Promise(resolve => setTimeout(resolve, 2000));
            } catch (e) {
                console.log('No location popup found or already handled');
            }

            // Wait for products to load - try multiple selectors
            try {
                await this.page.waitForSelector('.product-item, [class*="product"], .product-tile', { timeout: 15000 });
            } catch (e) {
                console.log('Products not found with primary selectors, trying alternatives...');
                await this.page.waitForSelector('img[alt*="Milk"], img[alt*="milk"]', { timeout: 10000 });
            }

            let products = [];
            let lastProductCount = 0;
            let scrollAttempts = 0;
            const maxScrollAttempts = 5;

            while (products.length < maxResults && scrollAttempts < maxScrollAttempts) {
                // Extract product information
                const newProducts = await this.page.evaluate((maxResults) => {
                    const results = [];
                    
                    // Try multiple approaches to find product containers
                    let productElements = [];
                    
                    // Strategy 1: Look for product containers with various class patterns
                    const containerSelectors = [
                        '.product-item',
                        '[class*="product-tile"]',
                        '[class*="product-card"]',
                        '[class*="product-item"]',
                        '[class*="product"]'
                    ];
                    
                    for (const selector of containerSelectors) {
                        productElements = document.querySelectorAll(selector);
                        if (productElements.length > 0) break;
                    }
                    
                    // Strategy 2: If no containers found, look for product links or images
                    if (productElements.length === 0) {
                        const linkElements = document.querySelectorAll('a[href*="product"], a:has(img[alt])');
                        productElements = Array.from(linkElements).map(link => {
                            // Find the closest container that might hold product info
                            return link.closest('div') || link;
                        });
                    }

                    for (let i = 0; i < Math.min(productElements.length, maxResults); i++) {
                        const element = productElements[i];
                        
                        try {
                            // Extract title - try multiple approaches
                            let title = '';
                            const titleSelectors = [
                                'a[href*="product"]',
                                'h3', 'h2', 'h4',
                                '[class*="title"]', '[class*="name"]',
                                'img[alt]'
                            ];
                            
                            for (const selector of titleSelectors) {
                                const titleElement = element.querySelector(selector);
                                if (titleElement) {
                                    if (selector === 'img[alt]') {
                                        title = titleElement.alt;
                                    } else {
                                        title = titleElement.textContent.trim();
                                    }
                                    if (title && title !== 'N/A') break;
                                }
                            }

                            // Extract price information
                            let priceText = '';
                            let numericPrice = 0;

                            // Get all text content and look for price patterns
                            const elementText = element.textContent || '';
                            const priceMatches = elementText.match(/\$[\d,]+\.?\d*/g);
                            if (priceMatches && priceMatches.length > 0) {
                                priceText = priceMatches[0];
                                numericPrice = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;
                            }

                            // Look for unit price patterns
                            let unitPriceText = '';
                            const unitPriceMatches = elementText.match(/\$[\d,]+\.?\d*\s*per\s*\w+|\$[\d,]+\.?\d*\s*\/\s*\w+/gi);
                            if (unitPriceMatches && unitPriceMatches.length > 0) {
                                unitPriceText = unitPriceMatches[0];
                            }

                            // Look for discount/save information
                            let discountText = '';
                            const saveMatches = elementText.match(/save\s*\$[\d,]+\.?\d*/gi);
                            if (saveMatches && saveMatches.length > 0) {
                                discountText = saveMatches[0];
                            }

                            // Extract image
                            const imageElement = element.querySelector('img');
                            const imageUrl = imageElement ? imageElement.src : '';

                            // Extract product URL
                            const linkElement = element.querySelector('a[href*="product"]') || 
                                              element.querySelector('a[href]');
                            let productUrl = '';
                            if (linkElement && linkElement.href) {
                                productUrl = linkElement.href.startsWith('http') ? 
                                           linkElement.href : 
                                           'https://www.igashop.com.au' + linkElement.href;
                            }

                            // Determine if in stock
                            let inStock = true;
                            const stockIndicators = elementText.toLowerCase();
                            if (stockIndicators.includes('out of stock') || 
                                stockIndicators.includes('unavailable') ||
                                stockIndicators.includes('sold out')) {
                                inStock = false;
                            }

                            // Check for add to cart button
                            const addButton = element.querySelector('button:contains("Add")') ||
                                            element.querySelector('[class*="add-to-cart"]') ||
                                            element.querySelector('button[class*="add"]');

                            // Extract brand from title
                            let brand = 'Unknown';
                            if (title) {
                                // Common brand extraction patterns
                                const brandPatterns = [
                                    /^([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+/,  // First word(s) before space
                                    /([A-Za-z]+)\s+/  // First word
                                ];
                                
                                for (const pattern of brandPatterns) {
                                    const match = title.match(pattern);
                                    if (match && match[1]) {
                                        brand = match[1];
                                        break;
                                    }
                                }
                            }

                            // Determine category based on title keywords
                            let category = 'Grocery';
                            if (title) {
                                const titleLower = title.toLowerCase();
                                if (titleLower.includes('milk') || titleLower.includes('dairy') || titleLower.includes('cheese')) {
                                    category = 'Dairy';
                                } else if (titleLower.includes('bread') || titleLower.includes('bakery')) {
                                    category = 'Bakery';
                                } else if (titleLower.includes('meat') || titleLower.includes('chicken') || titleLower.includes('beef')) {
                                    category = 'Meat';
                                } else if (titleLower.includes('fruit') || titleLower.includes('vegetable')) {
                                    category = 'Fresh Produce';
                                }
                            }

                            // Only add product if we have essential information
                            if (title && title !== 'N/A' && (priceText || numericPrice > 0)) {
                                const product = {
                                    title: title,
                                    store: 'IGA',
                                    price: priceText || `$${numericPrice.toFixed(2)}`,
                                    discountedPrice: discountText ? priceText : '',
                                    discount: discountText,
                                    numericPrice: numericPrice,
                                    inStock: inStock,
                                    unitPrice: unitPriceText,
                                    imageUrl: imageUrl,
                                    brand: brand,
                                    category: category,
                                    productUrl: productUrl,
                                    scraped_at: new Date().toISOString()
                                };

                                results.push(product);
                            }
                        } catch (error) {
                            console.error('Error extracting product data:', error);
                        }
                    }

                    return results;
                }, maxResults);

                // Filter out duplicates
                const uniqueNewProducts = newProducts.filter(np => !products.some(p => p.productUrl === np.productUrl));
                products.push(...uniqueNewProducts);

                if (products.length === lastProductCount) {
                    console.log("No new products loaded after scroll. Stopping.");
                    break;
                }
                lastProductCount = products.length;

                // Scroll down to load more products
                await this.page.evaluate("window.scrollTo(0, document.body.scrollHeight)");
                await new Promise(resolve => setTimeout(resolve, 2000));
                scrollAttempts++;
            }

            console.log(`Found ${products.length} products from IGA`);
            return products.slice(0, maxResults);

        } catch (error) {
            console.error('IGA scraping error:', error);
            return [];
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

