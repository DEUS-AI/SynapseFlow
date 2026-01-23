import React, { useState, useEffect } from 'react';
import { Card } from '../ui/card';
import { Database, Table as TableIcon, Columns, ChevronRight } from 'lucide-react';

interface Catalog {
  id: string;
  name: string;
}

interface Schema {
  id: string;
  name: string;
}

interface Column {
  id: string;
  name: string;
  data_type: string;
  nullable: boolean;
  description?: string;
}

interface Table {
  id: string;
  name: string;
  columns: Column[];
  row_count?: number;
  description?: string;
}

export function MetadataViewer() {
  const [catalogs, setCatalogs] = useState<Catalog[]>([]);
  const [selectedCatalog, setSelectedCatalog] = useState<string | null>(null);
  const [schemas, setSchemas] = useState<Schema[]>([]);
  const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState({ catalogs: true, schemas: false, tables: false });

  useEffect(() => {
    // Load catalogs on mount
    fetch('/api/metadata/catalogs')
      .then(res => res.json())
      .then(data => {
        setCatalogs(data);
        setLoading(prev => ({ ...prev, catalogs: false }));
      })
      .catch(err => {
        console.error('Failed to load catalogs:', err);
        setLoading(prev => ({ ...prev, catalogs: false }));
      });
  }, []);

  useEffect(() => {
    if (selectedCatalog) {
      setLoading(prev => ({ ...prev, schemas: true }));
      fetch(`/api/metadata/catalogs/${encodeURIComponent(selectedCatalog)}/schemas`)
        .then(res => res.json())
        .then(data => {
          setSchemas(data);
          setLoading(prev => ({ ...prev, schemas: false }));
        })
        .catch(err => {
          console.error('Failed to load schemas:', err);
          setLoading(prev => ({ ...prev, schemas: false }));
        });
    } else {
      setSchemas([]);
      setSelectedSchema(null);
      setTables([]);
    }
  }, [selectedCatalog]);

  useEffect(() => {
    if (selectedSchema) {
      setLoading(prev => ({ ...prev, tables: true }));
      fetch(`/api/metadata/schemas/${encodeURIComponent(selectedSchema)}/tables`)
        .then(res => res.json())
        .then(data => {
          setTables(data);
          setLoading(prev => ({ ...prev, tables: false }));
        })
        .catch(err => {
          console.error('Failed to load tables:', err);
          setLoading(prev => ({ ...prev, tables: false }));
        });
    } else {
      setTables([]);
    }
  }, [selectedSchema]);

  return (
    <div className="grid grid-cols-3 gap-6 h-full">
      {/* Catalogs */}
      <Card className="p-4 overflow-hidden flex flex-col">
        <div className="flex items-center gap-2 mb-4">
          <Database className="h-5 w-5 text-blue-600" />
          <h3 className="font-semibold">Catalogs</h3>
          <span className="text-xs text-gray-500">({catalogs.length})</span>
        </div>
        <div className="flex-1 overflow-y-auto space-y-2">
          {loading.catalogs ? (
            <p className="text-sm text-gray-600">Loading catalogs...</p>
          ) : catalogs.length === 0 ? (
            <p className="text-sm text-gray-600">No catalogs found. Upload a DDA first.</p>
          ) : (
            catalogs.map(catalog => (
              <button
                key={catalog.id}
                onClick={() => setSelectedCatalog(catalog.id)}
                className={`w-full text-left px-3 py-2 rounded transition flex items-center justify-between ${
                  selectedCatalog === catalog.id
                    ? 'bg-blue-100 text-blue-900 font-medium'
                    : 'hover:bg-gray-100'
                }`}
              >
                <span className="truncate">{catalog.name}</span>
                <ChevronRight className="h-4 w-4 flex-shrink-0" />
              </button>
            ))
          )}
        </div>
      </Card>

      {/* Schemas */}
      <Card className="p-4 overflow-hidden flex flex-col">
        <div className="flex items-center gap-2 mb-4">
          <TableIcon className="h-5 w-5 text-green-600" />
          <h3 className="font-semibold">Schemas</h3>
          {selectedCatalog && <span className="text-xs text-gray-500">({schemas.length})</span>}
        </div>
        <div className="flex-1 overflow-y-auto space-y-2">
          {!selectedCatalog ? (
            <p className="text-sm text-gray-600">Select a catalog to view schemas</p>
          ) : loading.schemas ? (
            <p className="text-sm text-gray-600">Loading schemas...</p>
          ) : schemas.length === 0 ? (
            <p className="text-sm text-gray-600">No schemas found</p>
          ) : (
            schemas.map(schema => (
              <button
                key={schema.id}
                onClick={() => setSelectedSchema(schema.id)}
                className={`w-full text-left px-3 py-2 rounded transition flex items-center justify-between ${
                  selectedSchema === schema.id
                    ? 'bg-green-100 text-green-900 font-medium'
                    : 'hover:bg-gray-100'
                }`}
              >
                <span className="truncate">{schema.name}</span>
                <ChevronRight className="h-4 w-4 flex-shrink-0" />
              </button>
            ))
          )}
        </div>
      </Card>

      {/* Tables & Columns */}
      <Card className="p-4 overflow-hidden flex flex-col">
        <div className="flex items-center gap-2 mb-4">
          <Columns className="h-5 w-5 text-orange-600" />
          <h3 className="font-semibold">Tables</h3>
          {selectedSchema && <span className="text-xs text-gray-500">({tables.length})</span>}
        </div>
        <div className="flex-1 overflow-y-auto space-y-4">
          {!selectedSchema ? (
            <p className="text-sm text-gray-600">Select a schema to view tables</p>
          ) : loading.tables ? (
            <p className="text-sm text-gray-600">Loading tables...</p>
          ) : tables.length === 0 ? (
            <p className="text-sm text-gray-600">No tables found</p>
          ) : (
            tables.map(table => (
              <div key={table.id} className="border rounded p-3 hover:border-orange-400 transition">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-sm">{table.name}</h4>
                  {table.row_count !== undefined && (
                    <span className="text-xs text-gray-600">{table.row_count} rows</span>
                  )}
                </div>
                {table.description && (
                  <p className="text-xs text-gray-600 mb-2">{table.description}</p>
                )}
                <div className="space-y-1">
                  {table.columns.map(column => (
                    <div key={column.id} className="text-xs flex justify-between items-center py-1 border-t">
                      <div className="flex items-center gap-2 flex-1">
                        <span className="font-mono font-medium">{column.name}</span>
                        {!column.nullable && (
                          <span className="text-red-600 text-[10px]">*</span>
                        )}
                      </div>
                      <span className="text-gray-600">{column.data_type}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
