const puppeteer = require('puppeteer');

class AldiScraper {
    constructor() {
        this.baseUrl = 'https://www.aldi.com.au';
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

            console.log(`Searching ALDI for "${query}"...`);
            
            // Navigate to the products page
            await this.page.goto(`${this.baseUrl}/products`, {
                waitUntil: 'networkidle2',
                timeout: 30000
            });

            // Wait for products to load
            try {
                await this.page.waitForSelector('a', { timeout: 15000 });
            } catch (error) {
                console.log('Waiting for page content to load...');
                await this.page.waitForTimeout(3000);
            }

            // Extract product data based on the actual ALDI website structure
            const products = await this.page.evaluate((query, maxResults) => {
                const searchTerm = query.toLowerCase();
                
                // Look for product links that contain price patterns and product names
                const productElements = Array.from(document.querySelectorAll('a')).filter(a => {
                    const text = a.textContent.trim();
                    const href = a.href;
                    
                    // Look for links that contain price patterns and product names
                    return text.includes('$') && 
                           text.length > 10 && 
                           !href.includes('#') &&
                           !text.toLowerCase().includes('feedback') &&
                           !text.toLowerCase().includes('home') &&
                           !text.toLowerCase().includes('catalogue') &&
                           text.toLowerCase().includes(searchTerm);
                });
                
                console.log(`Found ${productElements.length} product elements matching "${query}"`);
                const products = [];

                for (let i = 0; i < Math.min(productElements.length, maxResults); i++) {
                    const element = productElements[i];
                    if (!element) continue;

                    try {
                        const fullText = element.textContent.trim();
                        
                        // Parse the ALDI product format: "BRANDNAME Product Description $price"
                        const priceMatch = fullText.match(/\$(\d+\.?\d*)/);
                        const price = priceMatch ? `$${priceMatch[1]}` : '';
                        const numericPrice = priceMatch ? parseFloat(priceMatch[1]) : 0;
                        
                        // Extract brand (usually the first part in uppercase)
                        const brandMatch = fullText.match(/^([A-Z\s&]+?)([A-Z][a-z]|$)/);
                        const brand = brandMatch ? brandMatch[1].trim() : '';
                        
                        // Extract title (remove brand and price)
                        let title = fullText;
                        if (brand) {
                            title = title.replace(brand, '').trim();
                        }
                        if (priceMatch) {
                            title = title.replace(priceMatch[0], '').trim();
                        }
                        
                        // Clean up title
                        title = title.replace(/^\W+|\W+$/g, '').trim();
                        if (!title) {
                            title = fullText.substring(0, 50).trim();
                        }

                        // Extract image URL
                        const imgElement = element.querySelector('img');
                        const imageUrl = imgElement ? imgElement.src || imgElement.getAttribute('data-src') : '';

                        // Extract product URL
                        const productUrl = element.href;

                        // Determine category based on product name/brand
                        let category = 'Groceries';
                        if (title.toLowerCase().includes('organic')) {
                            category = 'Organic';
                        } else if (title.toLowerCase().includes('meat') || title.toLowerCase().includes('chicken') || title.toLowerCase().includes('beef')) {
                            category = 'Meat & Seafood';
                        } else if (title.toLowerCase().includes('fruit') || title.toLowerCase().includes('vegetable')) {
                            category = 'Fresh Produce';
                        } else if (title.toLowerCase().includes('dairy') || title.toLowerCase().includes('milk') || title.toLowerCase().includes('cheese')) {
                            category = 'Dairy';
                        }

                        if (title && price) {
                            products.push({
                                store: 'ALDI Australia',
                                title: title,
                                price: price,
                                discount: '',
                                discountedPrice: '',
                                numericPrice: numericPrice,
                                inStock: true, // ALDI generally shows only in-stock items
                                unitPrice: '',
                                imageUrl: imageUrl ? (imageUrl.startsWith('http') ? imageUrl : 'https://www.aldi.com.au' + imageUrl) : '',
                                productUrl: productUrl ? (productUrl.startsWith('http') ? productUrl : 'https://www.aldi.com.au' + productUrl) : '',
                                brand: brand,
                                category: category,
                                scraped_at: new Date().toISOString(),
                                rawText: fullText // For debugging
                            });
                        }
                    } catch (error) {
                        console.log('Error processing product element:', error);
                    }
                }

                return products;
            }, query, maxResults);

            // Sort by price (cheapest first)
            products.sort((a, b) => a.numericPrice - b.numericPrice);

            console.log(`Found ${products.length} products from ALDI matching "${query}"`);
            return products;

        } catch (error) {
            console.error('Error scraping ALDI:', error);
            return [];
        }
    }

    async getProductDetails(productUrl) {
        try {
            if (!this.browser) await this.init();

            await this.page.goto(productUrl, { waitUntil: 'networkidle2' });
            
            const productDetails = await this.page.evaluate(() => {
                // Extract detailed product information
                const title = document.querySelector('h1, .product-title, [class*="title"]')?.textContent?.trim();
                const description = document.querySelector('.product-description, [class*="description"]')?.textContent?.trim();
                const priceText = document.querySelector('[class*="price"], .price')?.textContent;
                const price = priceText?.match(/\$(\d+\.?\d*)/)?.[1];
                const images = Array.from(document.querySelectorAll('img'))
                    .map(img => img.src)
                    .filter(src => src && src.includes('product'));

                return {
                    title: title || '',
                    description: description || '',
                    price: price ? parseFloat(price) : null,
                    images: images,
                    nutritionalInfo: '',
                    ingredients: '',
                    brand: '',
                    size: '',
                    origin: ''
                };
            });

            return productDetails;
        } catch (error) {
            console.error('Error getting product details from ALDI:', error);
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

module.exports = AldiScraper;