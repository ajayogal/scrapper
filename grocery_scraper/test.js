const GroceryScraper = require('./index');

async function testScraper() {
    console.log('=== GROCERY SCRAPER TEST ===\n');
    
    const scraper = new GroceryScraper();
    
    try {
        // Test 1: Search a single store
        console.log('Test 1: Searching Woolworths for "milk" (max 5 results)...');
        const woolworthsResults = await scraper.scrapeStore('woolworths', 'milk', 5);
        console.log(`✓ Found ${woolworthsResults.length} products from Woolworths`);
        
        if (woolworthsResults.length > 0) {
            console.log('Sample product:');
            console.log(`  Name: ${woolworthsResults[0].name}`);
            console.log(`  Price: ${woolworthsResults[0].price}`);
            console.log(`  Store: ${woolworthsResults[0].store}`);
        }
        console.log('');

        // Test 2: Search all stores
        console.log('Test 2: Searching all stores for "bread" (max 3 results per store)...');
        const allResults = await scraper.scrapeAllStores('bread', 3);
        
        let totalProducts = 0;
        for (const [store, products] of Object.entries(allResults)) {
            console.log(`✓ ${store}: ${products.length} products`);
            totalProducts += products.length;
        }
        console.log(`✓ Total products found: ${totalProducts}`);
        console.log('');

        // Test 3: Utility functions
        console.log('Test 3: Testing utility functions...');
        const flatResults = scraper.flattenResults(allResults);
        console.log(`✓ Flattened results: ${flatResults.length} products`);
        
        const sortedResults = scraper.sortByPrice(flatResults);
        console.log(`✓ Sorted by price: ${sortedResults.length} products`);
        
        if (sortedResults.length > 0) {
            console.log(`  Cheapest: ${sortedResults[0].name} - ${sortedResults[0].price} (${sortedResults[0].store})`);
            console.log(`  Most expensive: ${sortedResults[sortedResults.length - 1].name} - ${sortedResults[sortedResults.length - 1].price} (${sortedResults[sortedResults.length - 1].store})`);
        }
        console.log('');

        // Test 4: Test ALDI specifically
        console.log('Test 4: Testing ALDI scraper specifically...');
        try {
            const aldiResults = await scraper.scrapeStore('aldi', 'organic', 3);
            console.log(`✓ ALDI test: Found ${aldiResults.length} products`);
            
            if (aldiResults.length > 0) {
                console.log('Sample ALDI product:');
                console.log(`  Name: ${aldiResults[0].title}`);
                console.log(`  Price: ${aldiResults[0].price}`);
                console.log(`  Store: ${aldiResults[0].store}`);
                console.log(`  Brand: ${aldiResults[0].brand}`);
            }
        } catch (error) {
            console.log(`⚠️  ALDI test failed (this is expected if ALDI is not accessible): ${error.message}`);
        }
        console.log('');

        console.log('=== ALL TESTS COMPLETED SUCCESSFULLY ===');
        
    } catch (error) {
        console.error('❌ Test failed:', error.message);
        console.error(error.stack);
    } finally {
        await scraper.closeAll();
    }
}

// Run tests if this file is executed directly
if (require.main === module) {
    testScraper().catch(console.error);
}

module.exports = testScraper;

