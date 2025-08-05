const puppeteer = require("puppeteer");

class ColesScraper {
  constructor() {
    this.browser = null;
    this.page = null;
  }

  async init() {
    this.browser = await puppeteer.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });
    this.page = await this.browser.newPage();

    // Set user agent to avoid detection
    await this.page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    );

    // Set viewport
    await this.page.setViewport({ width: 1280, height: 720 });
  }

  async searchProducts(query, maxResults = 20) {
    try {
      if (!this.browser) {
        await this.init();
      }

      const searchUrl = `https://www.coles.com.au/search/products?q=${encodeURIComponent(query)}`;
      console.log(`Scraping Coles: ${searchUrl}`);

      await this.page.goto(searchUrl, { waitUntil: "networkidle2", timeout: 60000 });

      // Wait for products to load
      await this.page.waitForSelector('[data-testid="product-tile"]', { timeout: 30000 });

      let products = [];
      let lastProductCount = 0;
      let scrollAttempts = 0;
      const maxScrollAttempts = 5; // Limit scroll attempts to prevent infinite loops

      while (products.length < maxResults && scrollAttempts < maxScrollAttempts) {
        // Evaluate products on the page
        const newProducts = await this.page.evaluate(() => {
          const scrapedProducts = [];
          // Coles product cards often have a data-testid attribute
          const productElements = document.querySelectorAll('[data-testid="product-tile"]'); 

          productElements.forEach((element) => {
            try {
              const titleElement = element.querySelector('h2 a') || element.querySelector('[data-testid="product-title"] a');
              const title = titleElement ? titleElement.textContent.trim() : "N/A";

              // Extract price from Coles structure
              let priceText = "N/A";
              let numericPrice = 0;
              
              const priceElement = element.querySelector('[data-testid="price"]');
              if (priceElement) {
                priceText = priceElement.textContent.trim();
                numericPrice = parseFloat(priceText.replace(/[^0-9.]/g, "")) || 0;
              }

              const imageUrlElement = element.querySelector("img[src]");
              const imageUrl = imageUrlElement ? imageUrlElement.src : "";

              const productUrlElement = element.querySelector("h2 a") || element.querySelector('[data-testid="product-title"] a');
              const productUrl = productUrlElement ? productUrlElement.href : "";

              // Check for out of stock indicator
              const inStock = !element.querySelector('[data-testid="product-unavailable"]');

              let discountedPrice = "";
              let discount = "";
              const wasPriceElement = element.querySelector('[data-testid="was-price"]');
              if (wasPriceElement) {
                const wasPriceText = wasPriceElement.textContent.trim();
                discountedPrice = priceText;
                const originalNumericPrice = parseFloat(wasPriceText.replace(/[^0-9.]/g, "")) || 0;
                if (originalNumericPrice > numericPrice) {
                  discount = `Save $${(originalNumericPrice - numericPrice).toFixed(2)}`;
                }
              }

              // Extract brand from title or specific element
              let brand = "Unknown Brand";
              const brandElement = element.querySelector('[data-testid="product-brand"]');
              if (brandElement) {
                brand = brandElement.textContent.trim();
              } else if (title) {
                // Extract brand from title (first word or two)
                const titleWords = title.split(' ');
                if (titleWords.length > 0) {
                  brand = titleWords[0];
                }
              }

              const unitPriceElement = element.querySelector('[data-testid="unit-price"]');
              const unitPrice = unitPriceElement ? unitPriceElement.textContent.trim() : "";

              scrapedProducts.push({
                title,
                store: "Coles",
                price: priceText,
                discountedPrice,
                discount,
                numericPrice,
                inStock,
                unitPrice,
                imageUrl,
                brand,
                category: "Grocery", // Default, can be improved with more specific selectors
                productUrl,
                scraped_at: new Date().toISOString(),
              });
            } catch (e) {
              console.error("Error parsing product element:", e);
            }
          });
          return scrapedProducts;
        });
        
        // Filter out duplicates if any (due to re-evaluation after scroll)
        const uniqueNewProducts = newProducts.filter(np => !products.some(p => p.productUrl === np.productUrl));
        products.push(...uniqueNewProducts);

        if (products.length === lastProductCount) {
          // No new products loaded after scroll, stop scrolling
          console.log("No new products loaded after scroll. Stopping.");
          break;
        }
        lastProductCount = products.length;

        // Scroll down to load more products
        await this.page.evaluate("window.scrollTo(0, document.body.scrollHeight)");
        await new Promise(resolve => setTimeout(resolve, 2000)); // Give time for content to load
        scrollAttempts++;
      }

      console.log(`Found ${products.length} products from Coles`);
      return products.slice(0, maxResults);

    } catch (error) {
      console.error("Coles scraping error:", error);
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

module.exports = ColesScraper;


