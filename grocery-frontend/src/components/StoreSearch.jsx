import { useState } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Loader2, Search, Store, Plus, X, ShoppingBag } from 'lucide-react'

function StoreSearch() {
  const [selectedStore, setSelectedStore] = useState('')
  const [searchTerms, setSearchTerms] = useState([''])
  const [dietaryPreference, setDietaryPreference] = useState('none')
  const [allProducts, setAllProducts] = useState([]) // All fetched products
  const [displayedProducts, setDisplayedProducts] = useState([]) // Currently displayed products
  const [loading, setLoading] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [itemsPerPage] = useState(10)
  const [currentDisplayCount, setCurrentDisplayCount] = useState(10)

  const stores = [
    { id: 'coles', name: 'Coles' },
    { id: 'woolworths', name: 'Woolworths' },
    { id: 'iga', name: 'IGA' },
    { id: 'aldi', name: 'Aldi' },
    { id: 'harris', name: 'Harris Farm Markets' }
  ]

  const dietaryPreferences = [
    { id: 'none', name: 'Any Groceries', description: 'General grocery items (both veg and non-veg)' },
    { id: 'vegetarian', name: 'Vegetarian', description: 'Vegetarian-friendly products' },
    { id: 'vegan', name: 'Vegan', description: 'Plant-based products only' },
    { id: 'gluten free', name: 'Gluten Free', description: 'Gluten-free products' },
    { id: 'others', name: 'Specialty/Organic', description: 'Organic, natural, and specialty products' }
  ]

  const addSearchTerm = () => {
    setSearchTerms([...searchTerms, ''])
  }

  const removeSearchTerm = (index) => {
    if (searchTerms.length > 1) {
      setSearchTerms(searchTerms.filter((_, i) => i !== index))
    }
  }

  const updateSearchTerm = (index, value) => {
    const updated = [...searchTerms]
    updated[index] = value
    setSearchTerms(updated)
  }

  const handleSearch = async () => {
    if (!selectedStore) {
      setSearchError('Please select a store')
      return
    }

    // All dietary preferences now have predefined search terms, no validation needed

    setLoading(true)
    setAllProducts([])
    setDisplayedProducts([])
    setCurrentDisplayCount(itemsPerPage)
    setSearchError('')

    try {
      const requestBody = {
        dietary_preference: dietaryPreference,
        // No pagination - get all products in one call
      }

      // All dietary preferences use predefined search terms, no manual search_terms needed

      console.log('Store Search Request:', {
        url: `http://localhost:5002/api/grocery/store/${selectedStore}`,
        body: requestBody
      })

      const response = await fetch(`http://localhost:5002/api/grocery/store/${selectedStore}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('API Response Error:', {
          status: response.status,
          statusText: response.statusText,
          body: errorText
        })
        throw new Error(`API Error ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      console.log('Store Search Response:', data)

      if (data.success) {
        const products = data.products || []
        setAllProducts(products)
        // Show first 10 items initially
        setDisplayedProducts(products.slice(0, itemsPerPage))
        setCurrentDisplayCount(Math.min(itemsPerPage, products.length))
      } else {
        throw new Error(data.error || 'Search failed')
      }
    } catch (error) {
      console.error('Store search failed:', error)
      setAllProducts([])
      setDisplayedProducts([])
      
      // More detailed error message
      if (error.message.includes('Failed to fetch')) {
        setSearchError('Unable to connect to the server. Please check if the API is running on http://localhost:5002')
      } else {
        setSearchError(`Search failed: ${error.message}. Please try again.`)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleLoadMore = () => {
    const newDisplayCount = currentDisplayCount + itemsPerPage
    setDisplayedProducts(allProducts.slice(0, newDisplayCount))
    setCurrentDisplayCount(newDisplayCount)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  // No grouping needed - display all products in a single grid

  return (
    <div className="space-y-6">
      {/* Search Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Store className="h-5 w-5" />
            Store-Specific Search
          </CardTitle>
          <CardDescription>
            Choose a dietary preference and get the cheapest products from a specific store
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Store Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Store
            </label>
            <Select value={selectedStore} onValueChange={setSelectedStore}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose a store to search" />
              </SelectTrigger>
              <SelectContent>
                {stores.map(store => (
                  <SelectItem key={store.id} value={store.id}>
                    {store.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Dietary Preference Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Dietary Preference
            </label>
            <Select value={dietaryPreference} onValueChange={setDietaryPreference}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose dietary preference" />
              </SelectTrigger>
              <SelectContent>
                {dietaryPreferences.map(pref => (
                  <SelectItem key={pref.id} value={pref.id}>
                    <div className="flex flex-col">
                      <span className="font-medium">{pref.name}</span>
                      <span className="text-xs text-gray-500">{pref.description}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Dietary Preference Info */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
            <h4 className="font-medium text-blue-900 mb-2">
              {dietaryPreferences.find(p => p.id === dietaryPreference)?.name} Search
            </h4>
            <p className="text-sm text-blue-700">
              We'll automatically search for {dietaryPreferences.find(p => p.id === dietaryPreference)?.description.toLowerCase()} 
              in {selectedStore ? stores.find(s => s.id === selectedStore)?.name : 'the selected store'}.
            </p>
          </div>

          {/* Search Button */}
          <Button 
            onClick={handleSearch}
            disabled={loading || !selectedStore}
            className="w-full"
            size="lg"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Searching {selectedStore}...
              </>
            ) : (
              <>
                <Search className="mr-2 h-4 w-4" />
                Search {selectedStore ? stores.find(s => s.id === selectedStore)?.name : 'Store'}
                ({dietaryPreferences.find(p => p.id === dietaryPreference)?.name})
              </>
            )}
          </Button>

          {/* Search Error */}
          {searchError && (
            <div className="p-3 bg-red-100 border border-red-200 rounded-md">
              <p className="text-red-700 text-sm">{searchError}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {loading && (
        <div className="text-center py-12">
          <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-blue-600" />
          <p className="text-lg text-gray-600">Searching {stores.find(s => s.id === selectedStore)?.name}...</p>
        </div>
      )}

      {!loading && displayedProducts.length > 0 && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <ShoppingBag className="h-6 w-6" />
              Search Results ({displayedProducts.length} of {allProducts.length} products)
            </h2>
            <div className="text-sm text-gray-600">
              From {stores.find(s => s.id === selectedStore)?.name}
            </div>
          </div>

          {/* All products in a single grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {displayedProducts.map((product, index) => (
              <Card key={`${product.title}-${index}`} className="hover:shadow-lg transition-shadow">
                <CardContent className="p-4">
                  {/* Product Image */}
                  <div className="aspect-square mb-3 bg-gray-100 rounded-lg overflow-hidden">
                    <img
                      src={product.imageUrl}
                      alt={product.title}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.src = "https://via.placeholder.com/150x150/E5E7EB/9CA3AF?text=No+Image"
                      }}
                    />
                  </div>

                  {/* Product Info */}
                  <div className="space-y-2">
                    <h4 className="font-semibold text-sm text-gray-900 line-clamp-2">
                      {product.title}
                    </h4>

                    {/* Store Badge with Logo */}
                    <div className="flex items-center gap-1">
                      {product.store_logo && (
                        <img
                          src={product.store_logo}
                          alt={`${product.store} logo`}
                          className="w-4 h-4 object-contain rounded"
                          onError={(e) => {
                            e.target.style.display = 'none';
                          }}
                        />
                      )}
                      <Badge variant="secondary" className="text-xs">
                        {product.store}
                      </Badge>
                    </div>

                    {/* Search Term Badge */}
                    {product.search_term && (
                      <Badge variant="outline" className="text-xs">
                        Found for: {product.search_term}
                      </Badge>
                    )}

                    {/* Price */}
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        {product.discountedPrice ? (
                          <>
                            <span className="text-lg font-bold text-green-600">
                              {product.discountedPrice}
                            </span>
                            <span className="text-sm line-through text-gray-500">
                              {product.price}
                            </span>
                          </>
                        ) : (
                          <span className="text-lg font-bold text-gray-900">
                            {product.price}
                          </span>
                        )}
                      </div>
                      
                      {product.unitPrice && (
                        <p className="text-xs text-gray-500">{product.unitPrice}</p>
                      )}
                    </div>

                    {/* Discount Badge */}
                    {product.discount && (
                      <Badge variant="destructive" className="text-xs">
                        {product.discount}
                      </Badge>
                    )}

                    {/* Stock Status */}
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${
                        product.inStock ? 'bg-green-500' : 'bg-red-500'
                      }`} />
                      <span className={`text-xs ${
                        product.inStock ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {product.inStock ? 'In Stock' : 'Out of Stock'}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Load More Button */}
          {currentDisplayCount < allProducts.length && (
            <div className="text-center mt-8">
              <Button 
                onClick={handleLoadMore}
                variant="outline"
                size="lg"
                className="px-8"
              >
                <Plus className="mr-2 h-4 w-4" />
                Load More Products
              </Button>
              <p className="text-sm text-gray-500 mt-2">
                Showing {displayedProducts.length} of {allProducts.length} products
              </p>
            </div>
          )}
        </div>
      )}

      {!loading && allProducts.length === 0 && selectedStore && (
        <div className="text-center py-12">
          {searchError ? (
            <>
              <div className="text-6xl mb-4">⚠️</div>
              <h3 className="text-xl font-semibold text-red-600 mb-2">Search Error</h3>
              <p className="text-gray-600">{searchError}</p>
            </>
          ) : (
            <>
              <div className="text-6xl mb-4">🔍</div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">No products found</h3>
              <p className="text-gray-600">
                No products found for your search terms in {stores.find(s => s.id === selectedStore)?.name}.
                Try different search terms.
              </p>
            </>
          )}
        </div>
      )}

      {!selectedStore && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">🏪</div>
          <h3 className="text-xl font-semibold text-gray-900 mb-2">Select a store to start</h3>
          <p className="text-gray-600">Choose a store and enter search terms to find the cheapest products.</p>
        </div>
      )}
    </div>
  )
}

export default StoreSearch
