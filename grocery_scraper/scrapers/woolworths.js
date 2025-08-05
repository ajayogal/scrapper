const puppeteer = require("puppeteer");

class WoolworthsScraper {
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

      const searchUrl = `https://www.woolworths.com.au/shop/search/products?searchTerm=${encodeURIComponent(
        query
      )}`;
      console.log(`Scraping Woolworths: ${searchUrl}`);

      await this.page.goto(searchUrl, { waitUntil: "networkidle2", timeout: 60000 });

      // Wait for the product grid to appear
      await this.page.waitForSelector(".product-grid", { timeout: 30000 });

      let products = [];
      let lastProductCount = 0;
      let scrollAttempts = 0;
      const maxScrollAttempts = 5; // Limit scroll attempts to prevent infinite loops

      while (products.length < maxResults && scrollAttempts < maxScrollAttempts) {
        // Evaluate products on the page
        const newProducts = await this.page.evaluate(() => {
          const scrapedProducts = [];
          const productElements = document.querySelectorAll(".product-tile"); // Adjust selector if needed

          productElements.forEach((element) => {
            try {
              const titleElement = element.querySelector(".product-title-link") || element.querySelector("h3 a");
              const title = titleElement ? titleElement.textContent.trim() : "N/A";

              const priceDollarsElement = element.querySelector(".price-dollars");
              const priceCentsElement = element.querySelector(".price-cents");
              let priceText = "N/A";
              let numericPrice = 0;

              if (priceDollarsElement && priceCentsElement) {
                priceText = `$${priceDollarsElement.textContent.trim()}.${priceCentsElement.textContent.trim()}`;
                numericPrice = parseFloat(`${priceDollarsElement.textContent.trim()}.${priceCentsElement.textContent.trim()}`);
              } else if (priceDollarsElement) {
                priceText = `$${priceDollarsElement.textContent.trim()}`;
                numericPrice = parseFloat(priceDollarsElement.textContent.trim());
              }

              const imageUrlElement = element.querySelector("img[data-src]") || element.querySelector("img[src]");
              const imageUrl = imageUrlElement ? (imageUrlElement.dataset.src || imageUrlElement.src) : "";

              const productUrlElement = element.querySelector(".product-title-link") || element.querySelector("a[href*=\"/shop/productdetails/\"]");
              const productUrl = productUrlElement ? productUrlElement.href : "";

              const inStock = !element.querySelector(".stock-status-label.out-of-stock");

              let discountedPrice = "";
              let discount = "";
              const wasPriceElement = element.querySelector(".price-was");
              if (wasPriceElement) {
                const originalPriceText = wasPriceElement.textContent.trim();
                const originalNumericPrice = parseFloat(originalPriceText.replace(/[^0-9.]/g, "")) || 0;
                if (originalNumericPrice > numericPrice) {
                  discountedPrice = priceText;
                  discount = `Save $${(originalNumericPrice - numericPrice).toFixed(2)}`;
                }
              }

              const brandElement = element.querySelector(".product-brand");
              const brand = brandElement ? brandElement.textContent.trim() : "Unknown Brand";

              const unitPriceElement = element.querySelector(".price-per-unit");
              const unitPrice = unitPriceElement ? unitPriceElement.textContent.trim() : "";

              scrapedProducts.push({
                title,
                store: "Woolworths",
                price: priceText,
                discountedPrice,
                discount,
                numericPrice,
                inStock,
                unitPrice,
                imageUrl,
                brand,
                category: "Grocery",
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

      console.log(`Found ${products.length} products from Woolworths`);
      return products.slice(0, maxResults);

    } catch (error) {
      console.error("Woolworths scraping error:", error);
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

module.exports = WoolworthsScraper;



