import React, { useState, useEffect } from 'react';
import { Search, Database, Table, Columns } from 'lucide-react';
import { Input } from '../ui/input';
import { Card } from '../ui/card';

interface CatalogItem {
  id: string;
  name: string;
  type: 'catalog' | 'schema' | 'table' | 'column';
  parent?: string;
  description?: string;
  data_type?: string;
  path: string[];
}

export function DataCatalog() {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [filteredItems, setFilteredItems] = useState<CatalogItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedType, setSelectedType] = useState<string>('all');

  useEffect(() => {
    // Load all catalog items
    fetch('/api/metadata/catalog/all')
      .then(res => res.json())
      .then(data => {
        setItems(data);
        setFilteredItems(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load catalog:', err);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    // Filter items based on search query and type
    let filtered = items;

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(item =>
        item.name.toLowerCase().includes(query) ||
        (item.description && item.description.toLowerCase().includes(query))
      );
    }

    if (selectedType !== 'all') {
      filtered = filtered.filter(item => item.type === selectedType);
    }

    setFilteredItems(filtered);
  }, [searchQuery, selectedType, items]);

  const getIcon = (type: string) => {
    switch (type) {
      case 'catalog':
        return <Database className="h-4 w-4 text-blue-600" />;
      case 'schema':
        return <Table className="h-4 w-4 text-green-600" />;
      case 'table':
        return <Table className="h-4 w-4 text-orange-600" />;
      case 'column':
        return <Columns className="h-4 w-4 text-purple-600" />;
      default:
        return null;
    }
  };

  const getTypeBadge = (type: string) => {
    const colors = {
      catalog: 'bg-blue-100 text-blue-800',
      schema: 'bg-green-100 text-green-800',
      table: 'bg-orange-100 text-orange-800',
      column: 'bg-purple-100 text-purple-800',
    };
    return colors[type as keyof typeof colors] || 'bg-gray-100 text-gray-800';
  };

  return (
    <Card className="p-6">
      <h2 className="text-xl font-semibold mb-4">Data Catalog Browser</h2>

      {/* Search and filters */}
      <div className="space-y-4 mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <Input
            placeholder="Search by name or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setSelectedType('all')}
            className={`px-3 py-1.5 text-sm rounded transition ${
              selectedType === 'all'
                ? 'bg-gray-900 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            All ({items.length})
          </button>
          <button
            onClick={() => setSelectedType('catalog')}
            className={`px-3 py-1.5 text-sm rounded transition ${
              selectedType === 'catalog'
                ? 'bg-blue-600 text-white'
                : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
            }`}
          >
            Catalogs
          </button>
          <button
            onClick={() => setSelectedType('schema')}
            className={`px-3 py-1.5 text-sm rounded transition ${
              selectedType === 'schema'
                ? 'bg-green-600 text-white'
                : 'bg-green-100 text-green-700 hover:bg-green-200'
            }`}
          >
            Schemas
          </button>
          <button
            onClick={() => setSelectedType('table')}
            className={`px-3 py-1.5 text-sm rounded transition ${
              selectedType === 'table'
                ? 'bg-orange-600 text-white'
                : 'bg-orange-100 text-orange-700 hover:bg-orange-200'
            }`}
          >
            Tables
          </button>
          <button
            onClick={() => setSelectedType('column')}
            className={`px-3 py-1.5 text-sm rounded transition ${
              selectedType === 'column'
                ? 'bg-purple-600 text-white'
                : 'bg-purple-100 text-purple-700 hover:bg-purple-200'
            }`}
          >
            Columns
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="space-y-2 max-h-[600px] overflow-y-auto">
        {loading ? (
          <p className="text-gray-600">Loading catalog...</p>
        ) : filteredItems.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-600">No items found</p>
            {searchQuery && (
              <p className="text-sm text-gray-500 mt-2">
                Try adjusting your search or filters
              </p>
            )}
          </div>
        ) : (
          filteredItems.map(item => (
            <div
              key={item.id}
              className="flex items-start gap-3 p-3 border rounded hover:border-gray-400 transition cursor-pointer"
            >
              <div className="mt-1">{getIcon(item.type)}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="font-medium truncate">{item.name}</h4>
                  <span className={`text-xs px-2 py-0.5 rounded ${getTypeBadge(item.type)}`}>
                    {item.type}
                  </span>
                  {item.data_type && (
                    <span className="text-xs text-gray-600 font-mono">
                      {item.data_type}
                    </span>
                  )}
                </div>
                {item.description && (
                  <p className="text-sm text-gray-600 mb-1">{item.description}</p>
                )}
                {item.path.length > 0 && (
                  <p className="text-xs text-gray-500">
                    📍 {item.path.join(' → ')}
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
