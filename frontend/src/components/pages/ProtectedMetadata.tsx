import React from 'react';
import { ProtectedPage } from '../auth/ProtectedPage';
import { MetadataViewer } from '../dda/MetadataViewer';

export function ProtectedMetadata() {
  return (
    <ProtectedPage>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 py-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Metadata Viewer</h1>
                <p className="mt-2 text-gray-600">Browse catalogs, schemas, tables, and columns</p>
              </div>
              <a
                href="/dda"
                className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition"
              >
                Back to DDA Management
              </a>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-6">
          <MetadataViewer />
        </main>
      </div>
    </ProtectedPage>
  );
}
