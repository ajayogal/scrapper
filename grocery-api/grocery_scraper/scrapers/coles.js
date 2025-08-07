const fs = require('fs').promises;
const path = require('path');

class ColesScraper {
    constructor() {
        console.log("INITEDDDD")
        this.mergedFilePath = path.join(__dirname, '..', '..', '..', 'generated', 'coles_merged_products.json');
    }

    async searchProducts(query, maxResults = 50) {
        try {
            const data = await fs.readFile(this.mergedFilePath, 'utf8');
            const allProducts = JSON.parse(data);
            console.log({mergedFilePath: this.mergedFilePath})
            console.log({query: query.toLowerCase()})
            console.log({allProducts})

            const filteredProducts = allProducts.filter(product => 
                product.title.toLowerCase().includes(query.toLowerCase())
            );
            console.log({filteredProducts})

            return filteredProducts.slice(0, maxResults);
        } catch (error) {
            if (error.code === 'ENOENT') {
                console.error(`Error: The file ${this.mergedFilePath} was not found.`);
                return [];
            } else {
                console.error('Error reading or parsing merged products file:', error);
                return [];
            }
        }
    }

    async close() {
        // No browser to close, so this is a no-op
    }
}

module.exports = ColesScraper;

