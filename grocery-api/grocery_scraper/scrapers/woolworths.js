const puppeteer = require('puppeteer');
const cheerio = require('cheerio');

class WoolworthsScraper {
    constructor() {
        this.baseUrl = 'https://www.woolworths.com.au';
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

    async searchProducts(query, maxResults = 50) {
        try {
            if (!this.browser) await this.init();

            const searchUrl = `${this.baseUrl}/shop/search/products?searchTerm=${encodeURIComponent(query)}`;
            await this.page.goto(searchUrl, { waitUntil: 'networkidle2' });

            // Wait for products to load - using more generic selectors
            await this.page.waitForSelector('a[href*="/product/"], .product-tile, [class*="product"]', { timeout: 15000 });

            const products = [];
            let currentResults = 0;

            while (currentResults < maxResults) {
                // Get current page content
                const content = await this.page.content();
                const $ = cheerio.load(content);

                // Extract products from current page using multiple selector strategies
                $('a[href*="/product/"]').each((index, element) => {
                    if (currentResults >= maxResults) return false;

                    const $product = $(element);
                    const $parent = $product.closest('[class*="product"], .product-tile, [data-testid*="product"]');
                    
                    // Try multiple ways to get product name
                    let name = $product.find('h3, h2, [class*="title"], [class*="name"]').text().trim();
                    if (!name) name = $product.text().trim().split('\n')[0];
                    
                    // Try multiple ways to get price
                    let priceText = $parent.find('[class*="price"]:not([class*="unit"]):not([class*="per"])').first().text().trim();
                    if (!priceText) priceText = $product.find('[class*="price"]:not([class*="unit"]):not([class*="per"])').first().text().trim();
                    
                    // Try to get unit price
                    let unitPriceText = $parent.find('[class*="unit"], [class*="per"]').text().trim();
                    if (!unitPriceText) unitPriceText = $product.find('[class*="unit"], [class*="per"]').text().trim();
                    
                    const imageUrl = $product.find('img').attr('src') || $parent.find('img').attr('src');
                    const productUrl = $product.attr('href');

                    if (name && priceText) {
                        // Extract discount information
                        let discount = '';
                        let discountedPrice = '';
                        let originalPrice = priceText;
                        
                        // Look for discount indicators
                        const discountElement = $parent.find('[class*="discount"], [class*="save"], [class*="was"]');
                        if (discountElement.length > 0) {
                            discount = discountElement.text().trim();
                            // Try to find original price
                            const wasPrice = $parent.find('[class*="was"], [class*="original"]').text().trim();
                            if (wasPrice) {
                                originalPrice = wasPrice;
                                discountedPrice = priceText;
                            }
                        }
                        
                        // Check stock status
                        let inStock = true;
                        const stockElement = $parent.find('[class*="out-of-stock"], [class*="unavailable"]');
                        if (stockElement.length > 0 || $parent.text().toLowerCase().includes('out of stock')) {
                            inStock = false;
                        }
                        
                        // Extract brand
                        let brand = '';
                        const brandElement = $parent.find('[class*="brand"]');
                        if (brandElement.length > 0) {
                            brand = brandElement.text().trim();
                        } else {
                            // Try to extract brand from product name
                            const nameParts = name.split(' ');
                            if (nameParts.length > 0) {
                                brand = nameParts[0];
                            }
                        }
                        
                        // Extract category (if available in breadcrumbs or navigation)
                        let category = '';
                        const categoryElement = $parent.find('[class*="category"], [class*="breadcrumb"]');
                        if (categoryElement.length > 0) {
                            category = categoryElement.text().trim();
                        }
                        
                        // Parse price for sorting
                        const numericPrice = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;

                        products.push({
                            store: 'Woolworths',
                            title: name,
                            price: originalPrice,
                            discount: discount,
                            discountedPrice: discountedPrice,
                            numericPrice: numericPrice,
                            inStock: inStock,
                            unitPrice: unitPriceText || '',
                            imageUrl: imageUrl ? (imageUrl.startsWith('http') ? imageUrl : (imageUrl.startsWith('//') ? 'https:' + imageUrl : this.baseUrl + imageUrl)) : '',
                            productUrl: productUrl ? (productUrl.startsWith('http') ? productUrl : this.baseUrl + productUrl) : '',
                            brand: brand,
                            category: category,
                            scraped_at: new Date().toISOString()
                        });
                        currentResults++;
                    }
                });

                // Try to load more products if available
                const loadMoreButton = await this.page.$('[data-testid="load-more-button"], button[class*="load"], button[class*="more"]');
                if (loadMoreButton && currentResults < maxResults) {
                    await loadMoreButton.click();
                    await new Promise(resolve => setTimeout(resolve, 2000)); // Wait for new products to load
                } else {
                    break;
                }
            }

            return products.slice(0, maxResults);
        } catch (error) {
            console.error('Error scraping Woolworths:', error);
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
                description: $('[data-testid="product-description"]').text().trim(),
                ingredients: $('[data-testid="product-ingredients"]').text().trim(),
                nutritionalInfo: $('[data-testid="nutritional-information"]').text().trim(),
                brand: $('[data-testid="product-brand"]').text().trim(),
                size: $('[data-testid="product-size"]').text().trim()
            };

            return details;
        } catch (error) {
            console.error('Error getting product details from Woolworths:', error);
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

module.exports = WoolworthsScraper;

