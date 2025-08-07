import React, { useState } from 'react';
import { Button } from '@/components/ui/button.jsx';
import { Input } from '@/components/ui/input.jsx';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx';
import { Loader2, Zap } from 'lucide-react';

const Merger = () => {
  const [folderName, setFolderName] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleMerge = async () => {
    setLoading(true);
    setMessage('');
    setError('');
    try {
      const response = await fetch(`http://localhost:5002/api/merger/${folderName}`, {
        method: 'POST',
      });

      const data = await response.json();

      if (response.ok) {
        setMessage(data.message);
      } else {
        setError(data.error || 'An error occurred.');
      }
    } catch (err) {
      setError('An error occurred while connecting to the server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="mb-8">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-5 w-5" />
          Merge Product Data
        </CardTitle>
        <CardDescription>
          Enter a folder name to merge all associated JSON files into a single file.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-4">
          <div className="flex-1">
            <Input
              type="text"
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              placeholder="Enter folder name (e.g., Coles)"
              className="text-lg"
            />
          </div>
          <Button onClick={handleMerge} disabled={loading || !folderName.trim()} className="px-8">
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Merging...
              </>
            ) : (
              <>
                <Zap className="mr-2 h-4 w-4" />
                Merge
              </>
            )}
          </Button>
        </div>
        {message && <p className="mt-4 text-green-600">{message}</p>}
        {error && <p className="mt-4 text-red-600">{error}</p>}
      </CardContent>
    </Card>
  );
};

export default Merger;
