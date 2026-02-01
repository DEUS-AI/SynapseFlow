import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  FileText,
  Network,
  Tags,
  BarChart3,
  Eye,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { DocumentOverviewTab } from './document-detail/DocumentOverviewTab';
import { DocumentGraphTab } from './document-detail/DocumentGraphTab';
import { DocumentEntitiesTab } from './document-detail/DocumentEntitiesTab';
import { DocumentQualityTab } from './document-detail/DocumentQualityTab';
import { DocumentPreviewTab } from './document-detail/DocumentPreviewTab';

interface DocumentDetailViewProps {
  docId: string;
}

interface DocumentData {
  id: string;
  filename: string;
  status: string;
  category?: string;
  created_at?: string;
  processed_at?: string;
  markdown_path?: string;
  entity_count?: number;
  relationship_count?: number;
  quality_score?: number;
  quality_level?: string;
}

type TabId = 'overview' | 'graph' | 'entities' | 'quality' | 'preview';

const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'overview', label: 'Overview', icon: <FileText className="w-4 h-4" /> },
  { id: 'graph', label: 'Knowledge Graph', icon: <Network className="w-4 h-4" /> },
  { id: 'entities', label: 'Entities', icon: <Tags className="w-4 h-4" /> },
  { id: 'quality', label: 'Quality', icon: <BarChart3 className="w-4 h-4" /> },
  { id: 'preview', label: 'Preview', icon: <Eye className="w-4 h-4" /> },
];

export function DocumentDetailView({ docId }: DocumentDetailViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [document, setDocument] = useState<DocumentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDocument() {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(`/api/admin/documents/${docId}`);
        if (!response.ok) {
          throw new Error('Document not found');
        }
        const data = await response.json();
        setDocument(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load document');
      } finally {
        setLoading(false);
      }
    }

    loadDocument();
  }, [docId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-slate-900">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <p className="text-slate-400">Loading document...</p>
        </div>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="flex items-center justify-center h-full bg-slate-900">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="w-12 h-12 text-red-500" />
          <div>
            <h2 className="text-xl font-semibold text-slate-200">Document Not Found</h2>
            <p className="text-slate-400 mt-2">{error || 'The requested document could not be loaded.'}</p>
          </div>
          <a
            href="/admin/documents"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Documents
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-slate-900">
      {/* Header */}
      <div className="flex-shrink-0 bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="flex items-center gap-4">
          <a
            href="/admin/documents"
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
            title="Back to documents"
          >
            <ArrowLeft className="w-5 h-5 text-slate-400" />
          </a>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-900/50 rounded-lg">
              <FileText className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-slate-100">{document.filename}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  document.status === 'completed' ? 'bg-green-900/50 text-green-400' :
                  document.status === 'processing' ? 'bg-blue-900/50 text-blue-400' :
                  document.status === 'failed' ? 'bg-red-900/50 text-red-400' :
                  'bg-slate-700 text-slate-400'
                }`}>
                  {document.status}
                </span>
                {document.category && (
                  <span className="text-xs text-slate-400">{document.category}</span>
                )}
                {document.entity_count !== undefined && (
                  <span className="text-xs text-slate-400">
                    {document.entity_count} entities
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4 -mb-4 border-b border-slate-700">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto p-6">
        {activeTab === 'overview' && (
          <DocumentOverviewTab document={document} />
        )}
        {activeTab === 'graph' && (
          <DocumentGraphTab docId={docId} />
        )}
        {activeTab === 'entities' && (
          <DocumentEntitiesTab docId={docId} />
        )}
        {activeTab === 'quality' && (
          <DocumentQualityTab docId={docId} />
        )}
        {activeTab === 'preview' && (
          <DocumentPreviewTab docId={docId} markdownPath={document.markdown_path} />
        )}
      </div>
    </div>
  );
}
