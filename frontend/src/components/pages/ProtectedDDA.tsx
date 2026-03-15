import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { DDAUploader } from '../dda/DDAUploader';
import { DataCatalog } from '../dda/DataCatalog';

export function ProtectedDDA() {
  return (
    <ProtectedPage>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 py-6">
            <h1 className="text-3xl font-bold text-gray-900">DDA Management</h1>
            <p className="mt-2 text-gray-600">Upload and manage Domain Data Architecture specifications</p>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <DDAUploader />

            <div className="space-y-4">
              <div className="bg-white p-6 rounded-lg shadow">
                <h3 className="font-semibold mb-2">Quick Links</h3>
                <div className="space-y-2">
                  <a
                    href="/dda/metadata"
                    className="block px-4 py-2 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition"
                  >
                    Metadata Viewer
                  </a>
                  <a
                    href="/graph"
                    className="block px-4 py-2 bg-green-50 text-green-700 rounded hover:bg-green-100 transition"
                  >
                    Knowledge Graph
                  </a>
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
                <h4 className="font-semibold text-blue-900 mb-2">What is a DDA?</h4>
                <p className="text-sm text-blue-800">
                  A <strong>Domain Data Architecture</strong> specification defines your data structure
                  in a human-readable markdown format. It includes catalogs, schemas, tables, columns,
                  and their relationships.
                </p>
              </div>
            </div>
          </div>

          <DataCatalog />
        </main>
      </div>
    </ProtectedPage>
  );
}
