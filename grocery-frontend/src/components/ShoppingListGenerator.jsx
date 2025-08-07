import React, { useState } from 'react';
import { Button } from '@/components/ui/button.jsx';
import { Input } from '@/components/ui/input.jsx';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx';
import { Badge } from '@/components/ui/badge.jsx';
import { Loader2, Package, TrendingUp, Plus, Trash2, DollarSign } from 'lucide-react';

const ShoppingListGenerator = () => {
  const [shoppingListSearchKeys, setShoppingListSearchKeys] = useState(['']);
  const [budget, setBudget] = useState(50);
  const [shoppingLists, setShoppingLists] = useState([]);
  const [generatingLists, setGeneratingLists] = useState(false);
  const [listError, setListError] = useState('');

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
          max_results_per_store: 50
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate shopping lists');
      }

      const data = await response.json();

      if (data.success) {
        setShoppingLists(data.lists || []);
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

            {/* Generate Button */}
            <Button
              onClick={generateShoppingLists}
              disabled={generatingLists || shoppingListSearchKeys.filter(k => k.trim()).length === 0 || budget <= 0}
              className="w-full"
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
          <h2 className="text-2xl font-bold text-gray-900">Your Optimized Shopping Lists</h2>
          <div className="grid gap-6 md:grid-cols-2">
            {shoppingLists.map((list, index) => (
              <Card key={index} className="overflow-hidden">
                <CardHeader className="bg-gradient-to-r from-blue-50 to-green-50">
                  <CardTitle className="flex items-center justify-between">
                    <span className="capitalize">{list.strategy.replace('_', ' ')}</span>
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
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {item.title}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="outline" className="text-xs">
                              {item.store}
                            </Badge>
                            <span className="text-sm font-semibold text-green-600">
                              {item.price}
                            </span>
                            {item.discount && (
                              <span className="text-xs text-red-600">
                                {item.discount}
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
