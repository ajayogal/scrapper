const puppeteer = require('puppeteer');
const cheerio = require('cheerio');

class HarrisScraper {
    constructor() {
        this.baseUrl = 'https://www.harrisfarm.com.au';
        this.browser = null;
        this.page = null;
    }

    async init() {
        this.browser = await puppeteer.launch({
            headless: true,
            args: [
                '--no-sandbox', 
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor',
                '--disable-web-security',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-gpu'
            ]
        });
        this.page = await this.browser.newPage();
        
        // Set more realistic browser properties
        await this.page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
        await this.page.setViewport({ width: 1366, height: 768 });
        
        // Remove webdriver property
        await this.page.evaluateOnNewDocument(() => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        });
        
        // Add realistic headers
        await this.page.setExtraHTTPHeaders({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        });
    }

    parseComplexPrice(priceString) {
        // Handle complex price strings like "Save $2.00 $8.99 ea $17.98 / kg"
        const result = {
            mainPrice: '',
            unitPrice: '',
            discount: '',
            originalPrice: ''
        };

        if (!priceString) return result;

        // Clean up the string
        const cleanPrice = priceString.replace(/\s+/g, ' ').trim();

        // Extract discount information (Save $X.XX or $X.XX off, etc.)
        const discountMatch = cleanPrice.match(/(?:save|off|discount)\s*\$?(\d+\.?\d*)/i);
        if (discountMatch) {
            result.discount = `$${discountMatch[1]}`;
        }

        // Extract all price patterns from the string
        const priceMatches = cleanPrice.match(/\$\d+\.?\d*/g) || [];
        
        if (priceMatches.length === 0) return result;

        // Strategy 1: If there's a discount mentioned, structure is usually:
        // "Save $X.XX $Y.YY ea $Z.ZZ / kg" where Y.YY is current price, Z.ZZ is unit price
        if (result.discount && priceMatches.length >= 2) {
            // Skip the discount amount (first price) and use the second as main price
            result.mainPrice = priceMatches[1];
            
            // Look for unit price pattern in the remaining string
            const afterMainPrice = cleanPrice.substring(cleanPrice.indexOf(result.mainPrice) + result.mainPrice.length);
            const unitPriceMatch = afterMainPrice.match(/\$(\d+\.?\d*)\s*\/?\s*(kg|g|each|ea|per|l|ml)/i);
            if (unitPriceMatch) {
                result.unitPrice = `$${unitPriceMatch[1]} / ${unitPriceMatch[2]}`;
            }
            
            // Calculate original price if we have discount
            const discountNum = parseFloat(result.discount.replace('$', ''));
            const currentNum = parseFloat(result.mainPrice.replace('$', ''));
            if (!isNaN(discountNum) && !isNaN(currentNum)) {
                result.originalPrice = `$${(currentNum + discountNum).toFixed(2)}`;
            }
        }
        // Strategy 2: Look for "ea" or "each" to identify main price vs unit price
        else if (cleanPrice.includes('ea') || cleanPrice.includes('each')) {
            // Find price that comes before "ea" or "each"
            const eachMatch = cleanPrice.match(/\$(\d+\.?\d*)\s*(?:ea|each)/i);
            if (eachMatch) {
                result.mainPrice = `$${eachMatch[1]}`;
                
                // Look for unit price (per kg, per g, etc.)
                const unitMatch = cleanPrice.match(/\$(\d+\.?\d*)\s*\/?\s*(kg|g|per|l|ml)/i);
                if (unitMatch && unitMatch[0] !== result.mainPrice) {
                    result.unitPrice = `$${unitMatch[1]} / ${unitMatch[2]}`;
                }
            }
        }
        // Strategy 3: Default - first price is main, look for unit price pattern
        else {
            result.mainPrice = priceMatches[0];
            
            // Look for unit price pattern
            const unitPriceMatch = cleanPrice.match(/\$(\d+\.?\d*)\s*\/?\s*(kg|g|each|ea|per|l|ml)/i);
            if (unitPriceMatch && unitPriceMatch[0] !== result.mainPrice) {
                result.unitPrice = `$${unitPriceMatch[1]} / ${unitPriceMatch[2]}`;
            }
        }

        return result;
    }

    async searchProducts(query, maxResults = 5) {
        try {
            if (!this.browser) await this.init();

            const searchUrl = `${this.baseUrl}/search?q=${encodeURIComponent(query)}&type=product%2Carticle%2Ccollection&options%5Bprefix%5D=last`;
            console.log(`Loading Harris Farm search page: ${searchUrl}`);
            
            // Navigate to page with longer timeout
            await this.page.goto(searchUrl, { 
                waitUntil: 'networkidle2', 
                timeout: 30000 
            });

            // Check if we're on a Cloudflare challenge page
            const title = await this.page.title();
            const bodyText = await this.page.evaluate(() => document.body.innerText.substring(0, 200));
            
            console.log(`Page title: ${title}`);
            console.log(`Body preview: ${bodyText}`);
            
            if (title.includes('Just a moment') || bodyText.includes('connection needs to be verified')) {
                console.log('Detected Cloudflare challenge, waiting...');
                // Wait longer for Cloudflare to complete
                await new Promise(resolve => setTimeout(resolve, 10000));
                
                // Try to wait for the page to redirect/reload after challenge
                try {
                    await this.page.waitForFunction(
                        () => !document.title.includes('Just a moment') && 
                              !document.body.innerText.includes('connection needs to be verified'),
                        { timeout: 30000 }
                    );
                    console.log('Cloudflare challenge completed');
                } catch (challengeError) {
                    console.log('Cloudflare challenge may still be active, continuing anyway...');
                }
            }

            // Wait for products to load - try multiple selector strategies
            let productsFound = false;
            const selectors = [
                'a[href*="/product"]',
                '.product',
                '[class*="product"]',
                '[data-testid*="product"]',
                '.ProductCard',
                '.product-item',
                '.search-result'
            ];
            
            for (const selector of selectors) {
                try {
                    await this.page.waitForSelector(selector, { timeout: 5000 });
                    console.log(`Found products using selector: ${selector}`);
                    productsFound = true;
                    break;
                } catch (selectorError) {
                    console.log(`Selector ${selector} not found, trying next...`);
                }
            }
            
            if (!productsFound) {
                console.log('No product selectors found, checking page content...');
                const content = await this.page.content();
                console.log(`Page content length: ${content.length}`);
                
                // If no products found, return empty array instead of throwing error
                if (content.length < 5000) {
                    console.log('Page content too short, likely blocked or error page');
                    return [];
                }
            }

            const products = [];
            const seenProducts = new Set(); // Track unique products
            let currentResults = 0;

            // For small numbers of products (<=50), just get the first page
            const shouldOnlyCheckFirstPage = maxResults <= 50;
            const maxPages = 10; // Safety limit: never go beyond 10 pages
            let pageCount = 0;
            
            while (currentResults < maxResults) {
                pageCount++;
                console.log(`Processing page ${pageCount}, found ${currentResults}/${maxResults} products so far...`);
                
                // Get current page content
                const content = await this.page.content();
                const $ = cheerio.load(content);

                // Look for product cards/containers that contain both name and price
                const productSelectors = [
                    '.product-card',
                    '.product-item', 
                    '[class*="product-card"]',
                    '[class*="ProductCard"]',
                    '[class*="product"]'
                ];
                
                let productElements = $();
                for (const selector of productSelectors) {
                    const elements = $(selector);
                    if (elements.length > 0) {
                        console.log(`Using selector: ${selector} (${elements.length} elements)`);
                        productElements = elements;
                        break;
                    }
                }
                
                // If no product containers found, fall back to product links
                if (productElements.length === 0) {
                    console.log('No product containers found, trying product links...');
                    productElements = $('a[href*="/product"]');
                }
                
                productElements.each((index, element) => {
                    if (currentResults >= maxResults) return false;

                    const $container = $(element);
                    
                    // Find product name within this container
                    let name = '';
                    const nameSelectors = ['h3', 'h2', '[class*="title"]', '[class*="name"]', '.product-title', 'a[href*="/product"]'];
                    for (const selector of nameSelectors) {
                        const nameEl = $container.find(selector).first();
                        if (nameEl.length > 0) {
                            name = nameEl.text().trim();
                            if (name && name.length > 3) break;
                        }
                    }
                    
                    // Clean up the name
                    if (name) {
                        name = name.replace(/\s+/g, ' ').trim();
                        // Remove any price-like text from the name
                        name = name.replace(/\$[\d,.]+.*$/g, '').trim();
                        if (name.length > 80) {
                            const words = name.split(' ');
                            name = words.slice(0, 6).join(' ');
                        }
                    }
                    
                    // Find price within this container - enhanced parsing
                    let priceText = '';
                    let unitPriceText = '';
                    let discountAmount = '';
                    
                    const priceElements = $container.find('[class*="price"]');
                    if (priceElements.length > 0) {
                        priceElements.each((i, priceEl) => {
                            const fullPriceText = $(priceEl).text().trim();
                            
                            // Parse complex price strings like "Save $2.00 $8.99 ea $17.98 / kg"
                            const parsedPrice = this.parseComplexPrice(fullPriceText);
                            
                            if (parsedPrice.mainPrice) {
                                priceText = parsedPrice.mainPrice;
                                if (parsedPrice.unitPrice) unitPriceText = parsedPrice.unitPrice;
                                if (parsedPrice.discount) discountAmount = parsedPrice.discount;
                                return false; // Break the loop
                            }
                            
                            // Fallback to simple price matching
                            if (fullPriceText.match(/\$\d+\.?\d*/)) {
                                priceText = fullPriceText;
                                return false;
                            }
                        });
                    }
                    
                    // Try to get unit price from separate elements if not found in main price
                    if (!unitPriceText) {
                        const unitPriceElements = $container.find('[class*="unit"], [class*="per"], [class*="kg"], [class*="each"]');
                        unitPriceElements.each((i, unitEl) => {
                            const unitText = $(unitEl).text().trim();
                            const unitMatch = unitText.match(/\$?(\d+\.?\d*)\s*(?:\/\s*)?(kg|g|each|ea|per)/i);
                            if (unitMatch) {
                                unitPriceText = `$${unitMatch[1]} / ${unitMatch[2]}`;
                                return false;
                            }
                        });
                    }
                    
                    // Extract only the numeric unit price for sorting/comparison
                    let unitPrice = '';
                    if (unitPriceText) {
                        const unitPriceMatch = unitPriceText.match(/\$?(\d+\.?\d*)/);
                        if (unitPriceMatch) {
                            unitPrice = unitPriceMatch[1];
                        }
                    }
                    
                    const imageUrl = $container.find('img').attr('src');
                    const productUrl = $container.find('a').first().attr('href') || ($container.is('a') ? $container.attr('href') : '');

                    // Debug logging for first few products
                    if (index < 5) {
                        console.log(`  Product ${index + 1}: name="${name}", price="${priceText}"`);
                    }
                    
                    if (name && priceText) {
                        // Create unique identifier for product
                        const productId = `${name.toLowerCase().trim()}-${priceText.replace(/[^0-9.]/g, '')}`;
                        
                        // Skip if we've already seen this product
                        if (seenProducts.has(productId)) {
                            return;
                        }
                        seenProducts.add(productId);
                        
                        // Extract discount information - use parsed data if available
                        let discount = discountAmount || '';
                        let discountedPrice = '';
                        let originalPrice = priceText;
                        
                        // If we parsed discount info from the price string, use it
                        if (discountAmount) {
                            const parsedPrice = this.parseComplexPrice(priceText);
                            if (parsedPrice.originalPrice) {
                                originalPrice = parsedPrice.originalPrice;
                                discountedPrice = priceText;
                            }
                        } else {
                            // Fallback to looking for discount indicators in separate elements
                            const discountElement = $container.find('[class*="discount"], [class*="save"], [class*="was"]');
                            if (discountElement.length > 0) {
                                discount = discountElement.text().trim();
                                // Try to find original price
                                const wasPrice = $container.find('[class*="was"], [class*="original"]').text().trim();
                                if (wasPrice) {
                                    originalPrice = wasPrice;
                                    discountedPrice = priceText;
                                }
                            }
                        }
                        
                        // Check stock status
                        let inStock = true;
                        const stockElement = $container.find('[class*="out-of-stock"], [class*="unavailable"]');
                        if (stockElement.length > 0 || $container.text().toLowerCase().includes('out of stock')) {
                            inStock = false;
                        }
                        
                        // Extract brand
                        let brand = '';
                        const brandElement = $container.find('[class*="brand"]');
                        if (brandElement.length > 0) {
                            brand = brandElement.text().trim();
                        } else {
                            // Try to extract brand from product name
                            const nameParts = name.split(' ');
                            if (nameParts.length > 0) {
                                brand = nameParts[0];
                            }
                        }
                        
                        // Extract category
                        let category = '';
                        const categoryElement = $container.find('[class*="category"], [class*="breadcrumb"]');
                        if (categoryElement.length > 0) {
                            category = categoryElement.text().trim();
                        }
                        
                        // Parse price for sorting
                        const numericPrice = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;

                        products.push({
                            store: 'Harris Farm Markets',
                            title: name,
                            price: originalPrice,
                            discount: discount,
                            discountedPrice: discountedPrice,
                            numericPrice: numericPrice,
                            inStock: inStock,
                            unitPrice: unitPrice || '',
                            unitPriceText: unitPriceText || '',
                            imageUrl: imageUrl ? (imageUrl.startsWith('http') ? imageUrl : (imageUrl.startsWith('//') ? 'https:' + imageUrl : this.baseUrl + imageUrl)) : '',
                            productUrl: productUrl ? (productUrl.startsWith('http') ? productUrl : this.baseUrl + productUrl) : '',
                            brand: brand,
                            category: category,
                            scraped_at: new Date().toISOString()
                        });
                        currentResults++;
                    }
                });

                // If we have enough products, should only check first page, or reached max pages, stop here
                if (currentResults >= maxResults || shouldOnlyCheckFirstPage || pageCount >= maxPages) {
                    if (pageCount >= maxPages) {
                        console.log(`Reached maximum page limit (${maxPages} pages). Got ${currentResults} products. Stopping.`);
                    } else {
                        console.log(`Got ${currentResults} products from ${pageCount} page(s). Stopping.`);
                    }
                    break;
                }

                // Try to scroll down to load more products (only for larger requests)
                console.log(`Need more products (${currentResults}/${maxResults}), trying to load more...`);
                const previousHeight = await this.page.evaluate('document.body.scrollHeight');
                await this.page.evaluate('window.scrollTo(0, document.body.scrollHeight)');
                await new Promise(resolve => setTimeout(resolve, 1500)); // Reduced wait time
                
                const newHeight = await this.page.evaluate('document.body.scrollHeight');
                
                if (newHeight === previousHeight && currentResults < maxResults) {
                    // Try to find and click next page button or load more button
                    const nextButton = await this.page.$('.pagination-next, [aria-label="Next page"], .load-more, button[class*="next"], button[class*="load"]');
                    if (nextButton) {
                        console.log('Clicking next page button...');
                        await nextButton.click();
                        await new Promise(resolve => setTimeout(resolve, 2000)); // Reduced wait time
                    } else {
                        console.log('No more pages available, stopping.');
                        break;
                    }
                }
            }

            return products.slice(0, maxResults);
        } catch (error) {
            console.error('Error scraping Harris Farm Markets:', error.message);
            
            // If it's a timeout or navigation error, try once more with different approach
            if (error.message.includes('TimeoutError') || error.message.includes('Navigation')) {
                console.log('Attempting alternative approach...');
                try {
                    // Try going to the main page first, then searching
                    await this.page.goto(this.baseUrl, { waitUntil: 'networkidle2', timeout: 20000 });
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    
                    // Check if there's a search form we can use
                    const searchInput = await this.page.$('input[type="search"], input[name="q"], .search-input');
                    if (searchInput) {
                        await searchInput.type(query);
                        await this.page.keyboard.press('Enter');
                        await new Promise(resolve => setTimeout(resolve, 5000));
                        
                        // Try to extract any products found
                        const content = await this.page.content();
                        const $ = cheerio.load(content);
                        
                        const products = [];
                        $('a[href*="/product"], [class*="product"], .product').slice(0, maxResults).each((index, element) => {
                            const $product = $(element);
                            const name = $product.find('h3, h2, [class*="title"], [class*="name"]').text().trim();
                            const priceText = $product.find('[class*="price"]').first().text().trim();
                            
                            if (name && priceText) {
                                products.push({
                                    store: 'Harris Farm Markets',
                                    title: name,
                                    price: priceText,
                                    discount: '',
                                    discountedPrice: '',
                                    numericPrice: parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0,
                                    inStock: true,
                                    unitPrice: '',
                                    imageUrl: '',
                                    productUrl: '',
                                    brand: '',
                                    category: '',
                                    scraped_at: new Date().toISOString()
                                });
                            }
                        });
                        
                        return products;
                    }
                } catch (retryError) {
                    console.error('Retry attempt also failed:', retryError.message);
                }
            }
            
            return [];
        }
    }

    async getProductDetails(productUrl) {
        try {
            if (!this.browser) await this.init();

            await this.page.goto(productUrl, { waitUntil: 'networkidle2' });
            
            const content = await this.page.content();
            const $ = cheerio.load(content);

            const details = {
                description: $('.product-description, .description').text().trim(),
                ingredients: $('.ingredients').text().trim(),
                nutritionalInfo: $('.nutritional-info, .nutrition').text().trim(),
                brand: $('.brand').text().trim(),
                size: $('.size, .pack-size').text().trim(),
                origin: $('.origin, .country-of-origin').text().trim()
            };

            return details;
        } catch (error) {
            console.error('Error getting product details from Harris Farm Markets:', error);
            return {};
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

module.exports = HarrisScraper;

