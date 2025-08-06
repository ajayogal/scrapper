import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Loader2, Search, ShoppingCart, Star, Filter, SortAsc, Plus, Trash2, RefreshCw } from 'lucide-react'
import './App.css'

function App() {
  const [searchQuery, setSearchQuery] = useState('')
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [selectedStore, setSelectedStore] = useState('all')
  const [sortBy, setSortBy] = useState('price')
  const [showInStockOnly, setShowInStockOnly] = useState(true)
  const [showDiscountedOnly, setShowDiscountedOnly] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [totalResults, setTotalResults] = useState(0)
  const [clearingCache, setClearingCache] = useState(false)
  const [cacheMessage, setCacheMessage] = useState('')
  const [searchError, setSearchError] = useState('')



  const handleSearch = async (resetProducts = true) => {
    if (!searchQuery.trim()) return
    
    if (resetProducts) {
      setLoading(true)
      setProducts([])
      setCurrentPage(1)
      setSearchError('') // Clear any previous errors
    } else {
      setLoadingMore(true)
    }
    
    try {
      const response = await fetch('http://localhost:5002/api/grocery/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: searchQuery,
          store: selectedStore,
          page: resetProducts ? 1 : currentPage + 1,
          perPage: 10
        })
      })
      
      if (!response.ok) {
        throw new Error('Search failed')
      }
      
      const data = await response.json()
      
      if (data.success) {
        if (resetProducts) {
          setProducts(data.products)
          setCurrentPage(1)
        } else {
          setProducts(prev => [...prev, ...data.products])
          setCurrentPage(prev => prev + 1)
        }
        setHasMore(data.hasMore)
        setTotalResults(data.totalResults)
      } else {
        throw new Error(data.error || 'Search failed')
      }
    } catch (error) {
      console.error('Search failed:', error)
      // Clear products on API failure - show no results
      if (resetProducts) {
        setProducts([])
        setHasMore(false)
        setTotalResults(0)
        setSearchError('Unable to search products. Please check your connection and try again.')
      }
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  const handleLoadMore = () => {
    handleSearch(false)
  }

  const handleClearCache = async () => {
    setClearingCache(true)
    setCacheMessage('')
    
    try {
      const response = await fetch('http://localhost:5002/api/grocery/cache/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to clear cache')
      }
      
      const data = await response.json()
      
      if (data.success) {
        setCacheMessage(data.message)
        // Clear the current search results to force fresh data on next search
        setProducts([])
        setTimeout(() => setCacheMessage(''), 3000) // Clear message after 3 seconds
      } else {
        throw new Error(data.error || 'Failed to clear cache')
      }
    } catch (error) {
      console.error('Cache clear failed:', error)
      setCacheMessage('Failed to clear cache. Please try again.')
      setTimeout(() => setCacheMessage(''), 3000)
    } finally {
      setClearingCache(false)
    }
  }

  const filteredAndSortedProducts = () => {
    let filtered = products

    // Filter by store
    if (selectedStore !== 'all') {
      filtered = filtered.filter(product => 
        product.store.toLowerCase().includes(selectedStore.toLowerCase())
      )
    }

    // Filter by stock status
    if (showInStockOnly) {
      filtered = filtered.filter(product => product.inStock)
    }

    // Filter by discount status
    if (showDiscountedOnly) {
      filtered = filtered.filter(product => product.discount && product.discount.length > 0)
    }

    // Sort products
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'price':
          return a.numericPrice - b.numericPrice
        case 'discount':
          // Sort by discount value (high to low)
          const getDiscountValue = (product) => {
            if (!product.discount || product.discount.length === 0) return 0
            
            // Extract numeric value from discount string
            const discountText = product.discount.toLowerCase()
            
            // Handle percentage discounts (e.g., "10% off", "20% Off")
            const percentMatch = discountText.match(/(\d+(?:\.\d+)?)%/)
            if (percentMatch) {
              return parseFloat(percentMatch[1])
            }
            
            // Handle dollar amount discounts (e.g., "Save $0.30", "$5 off")
            const dollarMatch = discountText.match(/\$(\d+(?:\.\d+)?)/)
            if (dollarMatch) {
              return parseFloat(dollarMatch[1])
            }
            
            // If discounted price exists, calculate percentage discount
            if (product.discountedPrice && product.price) {
              const originalPrice = parseFloat(product.price.replace(/[^0-9.]/g, ''))
              const discountedPrice = parseFloat(product.discountedPrice.replace(/[^0-9.]/g, ''))
              if (originalPrice > 0 && discountedPrice > 0) {
                return ((originalPrice - discountedPrice) / originalPrice) * 100
              }
            }
            
            return 0
          }
          
          return getDiscountValue(b) - getDiscountValue(a) // Descending order (high to low)
        case 'store':
          return a.store.localeCompare(b.store)
        case 'brand':
          return (a.brand || '').localeCompare(b.brand || '')
        default:
          return 0
      }
    })

    return filtered
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch(true)
    }
  }

  // Reset pagination when filters change
  useEffect(() => {
    if (products.length > 0) {
      // Don't reset if just changing filters, only if we need to search again
    }
  }, [selectedStore, sortBy, showInStockOnly, showDiscountedOnly])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-green-50 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-4 mb-4">
            <h1 className="text-4xl font-bold text-gray-900 flex items-center gap-2">
              <ShoppingCart className="h-8 w-8 text-green-600" />
              Grocery Price Comparison
            </h1>
            <Button
              onClick={handleClearCache}
              disabled={clearingCache}
              variant="outline"
              size="sm"
              className="ml-4"
              title="Clear cached search results to get fresh data from stores"
            >
              {clearingCache ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Clearing...
                </>
              ) : (
                <>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Clear Cache
                </>
              )}
            </Button>
          </div>
          <p className="text-lg text-gray-600">
            Find the best deals across Woolworths, Coles, IGA, and Harris Farm Markets
          </p>
          {cacheMessage && (
            <div className={`mt-2 p-2 rounded-md text-sm ${
              cacheMessage.includes('Failed') 
                ? 'bg-red-100 text-red-700 border border-red-200' 
                : 'bg-green-100 text-green-700 border border-green-200'
            }`}>
              {cacheMessage}
            </div>
          )}
        </div>

        {/* Search Section */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Search Products
            </CardTitle>
            <CardDescription>
              Enter a product name to compare prices across all stores
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 mb-4">
              <div className="flex-1">
                <Input
                  type="text"
                  placeholder="Search for products (e.g., milk, bread, eggs)"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={handleKeyPress}
                  className="text-lg"
                />
              </div>
              <Button 
                onClick={() => handleSearch(true)} 
                disabled={loading || !searchQuery.trim()}
                className="px-8"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="mr-2 h-4 w-4" />
                    Search
                  </>
                )}
              </Button>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-4 items-center">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-gray-500" />
                <span className="text-sm font-medium">Filters:</span>
              </div>
              
              <Select value={selectedStore} onValueChange={setSelectedStore}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Select store" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Stores</SelectItem>
                  <SelectItem value="woolworths">Woolworths</SelectItem>
                  <SelectItem value="coles">Coles</SelectItem>
                  <SelectItem value="iga">IGA</SelectItem>
                  <SelectItem value="harris">Harris Farm Markets</SelectItem>
                  <SelectItem value="aldi">Aldi</SelectItem>
                </SelectContent>
              </Select>

              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="price">Price (Low to High)</SelectItem>
                  <SelectItem value="discount">Discount (High to Low)</SelectItem>
                  <SelectItem value="store">Store Name</SelectItem>
                  <SelectItem value="brand">Brand</SelectItem>
                </SelectContent>
              </Select>

              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showInStockOnly}
                    onChange={(e) => setShowInStockOnly(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">In Stock Only</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showDiscountedOnly}
                    onChange={(e) => setShowDiscountedOnly(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Discounted Only</span>
                </label>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Results */}
        {loading && (
          <div className="text-center py-12">
            <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-blue-600" />
            <p className="text-lg text-gray-600">Searching across all stores...</p>
          </div>
        )}

        {!loading && products.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                Search Results ({filteredAndSortedProducts().length} of {totalResults} products)
              </h2>
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <SortAsc className="h-4 w-4" />
                Sorted by {sortBy === 'price' ? 'Price (Low to High)' : sortBy}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredAndSortedProducts().map((product, index) => (
                <Card key={`${product.store}-${product.title}-${index}`} className="hover:shadow-lg transition-shadow">
                  <CardContent className="p-4">
                    {/* Product Image */}
                    <div className="aspect-square mb-4 bg-gray-100 rounded-lg overflow-hidden">
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
                      <h3 className="font-semibold text-gray-900 line-clamp-2">
                        {product.title}
                      </h3>

                      {/* Store Badge */}
                      <Badge variant="secondary" className="text-xs">
                        {product.store}
                      </Badge>

                      {/* Brand and Category */}
                      {(product.brand || product.category) && (
                        <div className="flex gap-2 text-xs text-gray-500">
                          {product.brand && <span>Brand: {product.brand}</span>}
                          {product.category && <span>• {product.category}</span>}
                        </div>
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
                          <p className="text-xs text-gray-500 unit-price">{product.unitPrice}</p>
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
            {hasMore && (
              <div className="text-center mt-8">
                <Button 
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  variant="outline"
                  size="lg"
                  className="px-8"
                >
                  {loadingMore ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Loading More...
                    </>
                  ) : (
                    <>
                      <Plus className="mr-2 h-4 w-4" />
                      Load More Products
                    </>
                  )}
                </Button>
                <p className="text-sm text-gray-500 mt-2">
                  Showing {filteredAndSortedProducts().length} of {totalResults} products
                </p>
              </div>
            )}
          </div>
        )}

        {!loading && products.length === 0 && searchQuery && (
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
                <p className="text-gray-600">Try searching for a different product or check your spelling.</p>
              </>
            )}
          </div>
        )}

        {!loading && products.length === 0 && !searchQuery && (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">🛒</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Start your search</h3>
            <p className="text-gray-600">Enter a product name above to compare prices across all stores.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default App

