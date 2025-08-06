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
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        this.page = await this.browser.newPage();
        await this.page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36');
    }

    async searchProducts(query, maxResults = 5) {
        try {
            if (!this.browser) await this.init();

            const searchUrl = `${this.baseUrl}/search?q=${encodeURIComponent(query)}&type=product%2Carticle%2Ccollection&options%5Bprefix%5D=last`;
            await this.page.goto(searchUrl, { waitUntil: 'networkidle2' });

            // Wait for products to load - using more generic selectors
            await this.page.waitForSelector('a[href*="/product"], .product, [class*="product"]', { timeout: 15000 });

            const products = [];
            const seenProducts = new Set(); // Track unique products
            let currentResults = 0;

            while (currentResults < maxResults) {
                // Get current page content
                const content = await this.page.content();
                const $ = cheerio.load(content);

                // Extract products from current page using multiple selector strategies
                $('a[href*="/product"], [class*="product"], .product').each((index, element) => {
                    if (currentResults >= maxResults) return false;

                    const $product = $(element);
                    
                    // Try multiple ways to get product name
                    let name = $product.find('h3, h2, [class*="title"], [class*="name"]').text().trim();
                    if (!name) name = $product.text().trim().split('\n')[0];
                    
                    // Try multiple ways to get price
                    let priceText = $product.find('[class*="price"]:not([class*="unit"]):not([class*="per"])').first().text().trim();
                    
                    // Try to get unit price
                    let unitPriceText = $product.find('[class*="unit"], [class*="per"]').text().trim();
                    
                    // Extract only the numeric unit price
                    let unitPrice = '';
                    if (unitPriceText) {
                        // Match price patterns like $1.50, 1.50, $1.50/kg, $1.50 per kg, etc.
                        const unitPriceMatch = unitPriceText.match(/\$?(\d+\.?\d*)/);
                        if (unitPriceMatch) {
                            unitPrice = unitPriceMatch[1];
                        }
                    }
                    
                    const imageUrl = $product.find('img').attr('src');
                    const productUrl = $product.find('a').first().attr('href') || ($product.is('a') ? $product.attr('href') : '');

                    if (name && priceText) {
                        // Create unique identifier for product
                        const productId = `${name.toLowerCase().trim()}-${priceText.replace(/[^0-9.]/g, '')}`;
                        
                        // Skip if we've already seen this product
                        if (seenProducts.has(productId)) {
                            return;
                        }
                        seenProducts.add(productId);
                        
                        // Extract discount information
                        let discount = '';
                        let discountedPrice = '';
                        let originalPrice = priceText;
                        
                        // Look for discount indicators
                        const discountElement = $product.find('[class*="discount"], [class*="save"], [class*="was"]');
                        if (discountElement.length > 0) {
                            discount = discountElement.text().trim();
                            // Try to find original price
                            const wasPrice = $product.find('[class*="was"], [class*="original"]').text().trim();
                            if (wasPrice) {
                                originalPrice = wasPrice;
                                discountedPrice = priceText;
                            }
                        }
                        
                        // Check stock status
                        let inStock = true;
                        const stockElement = $product.find('[class*="out-of-stock"], [class*="unavailable"]');
                        if (stockElement.length > 0 || $product.text().toLowerCase().includes('out of stock')) {
                            inStock = false;
                        }
                        
                        // Extract brand
                        let brand = '';
                        const brandElement = $product.find('[class*="brand"]');
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
                        const categoryElement = $product.find('[class*="category"], [class*="breadcrumb"]');
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
                            imageUrl: imageUrl ? (imageUrl.startsWith('http') ? imageUrl : (imageUrl.startsWith('//') ? 'https:' + imageUrl : this.baseUrl + imageUrl)) : '',
                            productUrl: productUrl ? (productUrl.startsWith('http') ? productUrl : this.baseUrl + productUrl) : '',
                            brand: brand,
                            category: category,
                            scraped_at: new Date().toISOString()
                        });
                        currentResults++;
                    }
                });

                // Try to scroll down to load more products
                const previousHeight = await this.page.evaluate('document.body.scrollHeight');
                await this.page.evaluate('window.scrollTo(0, document.body.scrollHeight)');
                await new Promise(resolve => setTimeout(resolve, 2000));
                
                const newHeight = await this.page.evaluate('document.body.scrollHeight');
                
                if (newHeight === previousHeight && currentResults < maxResults) {
                    // Try to find and click next page button or load more button
                    const nextButton = await this.page.$('.pagination-next, [aria-label="Next page"], .load-more, button[class*="next"], button[class*="load"]');
                    if (nextButton) {
                        await nextButton.click();
                        await new Promise(resolve => setTimeout(resolve, 3000));
                    } else {
                        break;
                    }
                }
            }

            return products.slice(0, maxResults);
        } catch (error) {
            console.error('Error scraping Harris Farm Markets:', error);
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

