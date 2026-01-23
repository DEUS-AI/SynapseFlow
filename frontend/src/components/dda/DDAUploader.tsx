import React, { useState } from 'react';
import { Upload, CheckCircle, XCircle, FileText } from 'lucide-react';
import { Button } from '../ui/button';
import { Card } from '../ui/card';

interface UploadResult {
  success: boolean;
  message: string;
  entities_count?: number;
  relationships_count?: number;
  catalogs?: string[];
  schemas?: string[];
  tables?: string[];
}

export function DDAUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/dda/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setResult({
          success: true,
          message: `Successfully processed DDA specification!`,
          entities_count: data.entities_count,
          relationships_count: data.relationships_count,
          catalogs: data.catalogs || [],
          schemas: data.schemas || [],
          tables: data.tables || [],
        });
        setFile(null);
      } else {
        setResult({
          success: false,
          message: data.error || 'Failed to process DDA specification',
        });
      }
    } catch (error) {
      setResult({
        success: false,
        message: 'Network error. Please try again.',
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card className="p-6">
      <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
        <FileText className="h-5 w-5 text-purple-600" />
        Upload DDA Specification
      </h2>

      <div className="space-y-4">
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-purple-400 transition">
          <Upload className="h-12 w-12 mx-auto text-gray-400 mb-4" />
          <input
            type="file"
            accept=".md,.markdown"
            onChange={handleFileChange}
            className="hidden"
            id="dda-upload"
          />
          <label
            htmlFor="dda-upload"
            className="cursor-pointer text-purple-600 hover:text-purple-700 font-medium"
          >
            Choose DDA file
          </label>
          <p className="text-sm text-gray-600 mt-2">
            Markdown files (.md) only
          </p>
          {file && (
            <div className="mt-4 p-3 bg-purple-50 rounded inline-block">
              <p className="text-sm font-medium text-purple-900">
                📄 {file.name}
              </p>
              <p className="text-xs text-gray-600">
                {(file.size / 1024).toFixed(2)} KB
              </p>
            </div>
          )}
        </div>

        <Button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="w-full"
        >
          {uploading ? 'Processing...' : 'Upload and Process'}
        </Button>

        {result && (
          <div className={`flex items-start gap-3 p-4 rounded ${
            result.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
          }`}>
            {result.success ? (
              <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 flex-shrink-0" />
            ) : (
              <XCircle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1">
              <p className={`text-sm font-medium ${result.success ? 'text-green-700' : 'text-red-700'}`}>
                {result.message}
              </p>
              {result.success && (
                <div className="mt-3 space-y-2">
                  {result.entities_count !== undefined && (
                    <div className="text-sm text-green-700">
                      ✓ Created {result.entities_count} entities
                    </div>
                  )}
                  {result.relationships_count !== undefined && (
                    <div className="text-sm text-green-700">
                      ✓ Created {result.relationships_count} relationships
                    </div>
                  )}
                  {result.catalogs && result.catalogs.length > 0 && (
                    <div className="text-sm text-green-700">
                      ✓ Catalogs: {result.catalogs.join(', ')}
                    </div>
                  )}
                  {result.schemas && result.schemas.length > 0 && (
                    <div className="text-sm text-green-700">
                      ✓ Schemas: {result.schemas.join(', ')}
                    </div>
                  )}
                  {result.tables && result.tables.length > 0 && (
                    <div className="text-sm text-green-700">
                      ✓ Tables: {result.tables.join(', ')}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="mt-6 pt-6 border-t">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">What is a DDA?</h3>
        <p className="text-sm text-gray-600">
          A <strong>Domain Data Architecture (DDA)</strong> specification is a markdown document
          that describes the structure of your data domains, including catalogs, schemas, tables,
          and columns. Upload your DDA to automatically generate the metadata graph.
        </p>
      </div>
    </Card>
  );
}
