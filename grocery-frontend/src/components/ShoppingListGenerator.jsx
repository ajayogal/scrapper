import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button.jsx';
import { Input } from '@/components/ui/input.jsx';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx';
import { Badge } from '@/components/ui/badge.jsx';
import { Checkbox } from '@/components/ui/checkbox.jsx';
import { Loader2, Package, TrendingUp, Plus, Trash2, DollarSign, Store } from 'lucide-react';

const ShoppingListGenerator = () => {
  const [shoppingListSearchKeys, setShoppingListSearchKeys] = useState(['']);
  const [budget, setBudget] = useState(50);
  const [shoppingLists, setShoppingLists] = useState([]);
  const [generatingLists, setGeneratingLists] = useState(false);
  const [loadingMoreLists, setLoadingMoreLists] = useState(false);
  const [listError, setListError] = useState('');
  const [availableStores, setAvailableStores] = useState([]);
  const [selectedStores, setSelectedStores] = useState(['all']);
  const [loadingStores, setLoadingStores] = useState(true);
  const [usedProducts, setUsedProducts] = useState([]);
  const [usedNames, setUsedNames] = useState([]);
  const [canLoadMore, setCanLoadMore] = useState(false);

  // Fetch available stores on component mount
  useEffect(() => {
    const fetchStores = async () => {
      try {
        const response = await fetch('http://localhost:5002/api/grocery/stores');
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            setAvailableStores(data.stores);
          }
        }
      } catch (error) {
        console.error('Failed to fetch stores:', error);
      } finally {
        setLoadingStores(false);
      }
    };

    fetchStores();
  }, []);

  const addSearchKey = () => {
    setShoppingListSearchKeys([...shoppingListSearchKeys, '']);
  };

  const removeSearchKey = (index) => {
    if (shoppingListSearchKeys.length > 1) {
      setShoppingListSearchKeys(shoppingListSearchKeys.filter((_, i) => i !== index));
    }
  };

  const updateSearchKey = (index, value) => {
    const newKeys = [...shoppingListSearchKeys];
    newKeys[index] = value;
    setShoppingListSearchKeys(newKeys);
  };

  const handleStoreSelection = (storeId) => {
    if (storeId === 'all') {
      // If "All Stores" is selected, clear other selections
      setSelectedStores(['all']);
    } else {
      // If a specific store is selected
      const newSelectedStores = selectedStores.includes('all') 
        ? [storeId] // Remove "all" if it was selected
        : selectedStores.includes(storeId)
          ? selectedStores.filter(id => id !== storeId) // Remove if already selected
          : [...selectedStores, storeId]; // Add if not selected
      
      // If no specific stores are selected, default to "all"
      setSelectedStores(newSelectedStores.length === 0 ? ['all'] : newSelectedStores);
    }
  };

  const generateShoppingLists = async () => {
    const validKeys = shoppingListSearchKeys.filter(key => key.trim() !== '');
    if (validKeys.length === 0 || budget <= 0) return;

    setGeneratingLists(true);
    setListError('');

    try {
      const response = await fetch('http://localhost:5002/api/grocery/auto-generated-list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          search_keys: validKeys,
          budget: parseFloat(budget),
          max_results_per_store: 50,
          selected_stores: selectedStores
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate shopping lists');
      }

      const data = await response.json();

      if (data.success) {
        setShoppingLists(data.lists || []);
        setUsedProducts(data.used_products || []);
        setUsedNames(data.used_names || []);
        setCanLoadMore(true);
      } else {
        throw new Error(data.error || 'Failed to generate shopping lists');
      }
    } catch (error) {
      console.error('List generation failed:', error);
      setListError(error.message || 'Failed to generate shopping lists. Please try again.');
    } finally {
      setGeneratingLists(false);
    }
  };

  const loadMoreShoppingLists = async () => {
    const validKeys = shoppingListSearchKeys.filter(key => key.trim() !== '');
    if (validKeys.length === 0 || budget <= 0) return;

    setLoadingMoreLists(true);
    setListError('');

    try {
      const response = await fetch('http://localhost:5002/api/grocery/auto-generated-list/more', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          search_keys: validKeys,
          budget: parseFloat(budget),
          max_results_per_store: 50,
          selected_stores: selectedStores,
          used_products: usedProducts,
          used_names: usedNames
        })
      });

      if (!response.ok) {
        throw new Error('Failed to load more shopping lists');
      }

      const data = await response.json();

      if (data.success) {
        setShoppingLists(prevLists => [...prevLists, ...data.lists]);
        setUsedProducts(data.used_products || []);
        setUsedNames(data.used_names || []);
      } else {
        throw new Error(data.error || 'Failed to load more shopping lists');
      }
    } catch (error) {
      console.error('Load more failed:', error);
      setListError(error.message || 'Failed to load more shopping lists. Please try again.');
    } finally {
      setLoadingMoreLists(false);
    }
  };

  const createNewShoppingLists = async () => {
    const validKeys = shoppingListSearchKeys.filter(key => key.trim() !== '');
    if (validKeys.length === 0 || budget <= 0) return;

    setGeneratingLists(true);
    setListError('');

    try {
      const response = await fetch('http://localhost:5002/api/grocery/auto-generated-list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          search_keys: validKeys,
          budget: parseFloat(budget),
          max_results_per_store: 50,
          selected_stores: selectedStores
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate new shopping lists');
      }

      const data = await response.json();

      if (data.success) {
        setShoppingLists(data.lists || []);
        setUsedProducts(data.used_products || []);
        setUsedNames(data.used_names || []);
        setCanLoadMore(true);
      } else {
        throw new Error(data.error || 'Failed to generate new shopping lists');
      }
    } catch (error) {
      console.error('New list generation failed:', error);
      setListError(error.message || 'Failed to generate new shopping lists. Please try again.');
    } finally {
      setGeneratingLists(false);
    }
  };

  return (
    <div>
      {/* Shopping List Generator */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            Auto-Generated Shopping Lists
          </CardTitle>
          <CardDescription>
            Enter your shopping needs and budget to get 4 optimized shopping lists
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Search Keys */}
            <div>
              <label className="text-sm font-medium mb-2 block">What do you need to buy?</label>
              {shoppingListSearchKeys.map((key, index) => (
                <div key={index} className="flex gap-2 mb-2">
                  <Input
                    type="text"
                    placeholder="e.g., milk, bread, eggs"
                    value={key}
                    onChange={(e) => updateSearchKey(index, e.target.value)}
                    className="flex-1"
                  />
                  {shoppingListSearchKeys.length > 1 && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => removeSearchKey(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={addSearchKey}
                className="mt-2"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Item
              </Button>
            </div>

            {/* Budget */}
            <div>
              <label className="text-sm font-medium mb-2 block">Budget</label>
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-gray-500" />
                <Input
                  type="number"
                  placeholder="50"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  className="w-32"
                  min="1"
                  step="0.01"
                />
              </div>
            </div>

            {/* Store Selection */}
            <div>
              <label className="text-sm font-medium mb-2 block flex items-center gap-2">
                <Store className="h-4 w-4" />
                Choose Stores
              </label>
              {loadingStores ? (
                <div className="flex items-center gap-2 text-gray-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading stores...
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {availableStores.map((store) => (
                    <div key={store.id} className="flex items-center space-x-2">
                      <Checkbox 
                        id={store.id}
                        checked={selectedStores.includes(store.id)}
                        onCheckedChange={() => handleStoreSelection(store.id)}
                      />
                      <label 
                        htmlFor={store.id} 
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                      >
                        {store.name}
                      </label>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Generate Button */}
            <div className="flex flex-col sm:flex-row gap-3">
              <Button
                onClick={generateShoppingLists}
                disabled={generatingLists || shoppingListSearchKeys.filter(k => k.trim()).length === 0 || budget <= 0}
                className="w-full sm:w-auto"
              >
                {generatingLists ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating Lists...
                  </>
                ) : (
                  <>
                    <TrendingUp className="mr-2 h-4 w-4" />
                    Generate Shopping Lists
                  </>
                )}
              </Button>

              {shoppingLists.length > 0 && (
                <>
                  <Button 
                    onClick={loadMoreShoppingLists}
                    disabled={loadingMoreLists || !canLoadMore}
                    variant="outline"
                    className="w-full sm:w-auto"
                  >
                    {loadingMoreLists ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Loading More...
                      </>
                    ) : (
                      <>
                        <Plus className="mr-2 h-4 w-4" />
                        Load More 4 Lists
                      </>
                    )}
                  </Button>

                  <Button 
                    onClick={createNewShoppingLists}
                    disabled={generatingLists}
                    variant="secondary"
                    className="w-full sm:w-auto"
                  >
                    {generatingLists ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      <>
                        <Package className="mr-2 h-4 w-4" />
                        Create New 4 Lists
                      </>
                    )}
                  </Button>
                </>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* List Error */}
      {listError && (
        <div className="mb-6 p-4 bg-red-100 border border-red-200 rounded-md">
          <p className="text-red-700">{listError}</p>
        </div>
      )}

      {/* Generated Lists */}
      {shoppingLists.length > 0 && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900">Your Optimized Shopping Lists</h2>
            <div className="text-sm text-gray-600">
              <span className="font-medium">{shoppingLists.length} lists generated</span>
              {usedProducts.length > 0 && (
                <span className="ml-2">• {usedProducts.length} unique products used</span>
              )}
            </div>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            {shoppingLists.map((list, index) => (
              <Card key={index} className="overflow-hidden">
                <CardHeader className="bg-gradient-to-r from-blue-50 to-green-50">
                  <div className="flex items-start gap-4">
                    {/* List Image */}
                    {list.list_image && (
                      <div className="flex-shrink-0">
                        <img
                          src={list.list_image}
                          alt={`${list.strategy} list`}
                          className="w-16 h-16 object-cover rounded-lg border-2 border-white shadow-md"
                          onError={(e) => {
                            e.target.style.display = 'none';
                          }}
                        />
                      </div>
                    )}
                    
                    {/* List Details */}
                    <div className="flex-1 min-w-0">
                      <CardTitle className="flex items-center justify-between">
                        <span className="font-bold text-lg">{list.name || list.strategy.replace('_', ' ')}</span>
                        <Badge variant="secondary">{list.items_count} items</Badge>
                      </CardTitle>
                      <CardDescription>{list.description}</CardDescription>
                      <div className="flex justify-between items-center mt-2">
                        <span className="text-lg font-semibold text-green-600">
                          ${list.total_cost.toFixed(2)}
                        </span>
                        <span className="text-sm text-gray-500">
                          ${list.remaining_budget.toFixed(2)} remaining
                        </span>
                      </div>
                      {/* Display savings information */}
                      {list.total_savings > 0 && (
                        <div className="flex items-center gap-2 mt-2 p-2 bg-red-50 rounded-md">
                          <DollarSign className="h-4 w-4 text-red-600" />
                          <span className="text-sm font-semibold text-red-600">
                            Total Saved: ${list.total_savings.toFixed(2)}
                          </span>
                          <span className="text-xs text-gray-600">
                            ({list.discounted_items_count} discounted items)
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-4">
                  <div className="max-h-96 overflow-y-auto space-y-2">
                    {list.items.map((item, itemIndex) => (
                      <div key={itemIndex} className="flex items-center gap-3 p-2 bg-gray-50 rounded-md">
                        {item.imageUrl && (
                          <img
                            src={item.imageUrl}
                            alt={item.title}
                            className="w-12 h-12 object-cover rounded"
                            onError={(e) => {
                              e.target.style.display = 'none';
                            }}
                          />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-gray-900 truncate">
                              {item.title}
                            </p>
                            {(item.discountedPrice || item.discount) && (
                              <Badge variant="destructive" className="text-xs">
                                DISCOUNT
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <div className="flex items-center gap-1">
                              {item.store_logo && (
                                <img
                                  src={item.store_logo}
                                  alt={`${item.store} logo`}
                                  className="w-4 h-4 object-contain rounded"
                                  onError={(e) => {
                                    e.target.style.display = 'none';
                                  }}
                                />
                              )}
                              <Badge variant="outline" className="text-xs">
                                {item.store}
                              </Badge>
                            </div>
                            <span className="text-sm font-semibold text-green-600">
                              {item.price}
                            </span>
                            {item.discount && (
                              <span className="text-xs text-red-600 line-through">
                                {item.discount}
                              </span>
                            )}
                            {item.discountedPrice && (
                              <span className="text-xs text-red-600">
                                Sale: {item.discountedPrice}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ShoppingListGenerator;
