import React, { useState, useEffect, useCallback } from 'react';
import {
  Search, Upload, Trash2, Play, Eye, FileText,
  CheckCircle, XCircle, Clock, Loader2, RefreshCw,
  FolderOpen, Filter, BarChart3, AlertTriangle, AlertCircle,
  ExternalLink
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card } from '../ui/card';

interface Document {
  id: string;
  filename: string;
  path: string;
  category: string;
  size_bytes: number;
  status: 'not_started' | 'processing' | 'completed' | 'failed';
  ingested_at: string | null;
  entity_count: number;
  relationship_count: number;
  error_message: string | null;
  markdown_path: string | null;
  quality_score: number | null;
  quality_level: string | null;
}

interface Job {
  job_id: string;
  document_id: string;
  filename: string;
  status: string;
  progress: number;
  message: string;
}

interface Statistics {
  total: number;
  not_started: number;
  processing: number;
  completed: number;
  failed: number;
  total_entities: number;
  total_relationships: number;
  with_markdown: number;
}

export function DocumentManagement() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [activeJobs, setActiveJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');

  // Modal states
  const [showUploader, setShowUploader] = useState(false);
  const [showDetails, setShowDetails] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null);
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState<string | null>(null);

  const fetchDocuments = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (categoryFilter) params.append('category', categoryFilter);
      if (searchQuery) params.append('search', searchQuery);

      const response = await fetch(`/api/admin/documents?${params}`);
      if (response.ok) {
        const data = await response.json();
        setDocuments(data);
      }
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, categoryFilter, searchQuery]);

  const fetchStatistics = async () => {
    try {
      const response = await fetch('/api/admin/documents/statistics');
      if (response.ok) {
        const data = await response.json();
        setStatistics(data);
      }
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
    }
  };

  const fetchCategories = async () => {
    try {
      const response = await fetch('/api/admin/documents/categories');
      if (response.ok) {
        const data = await response.json();
        setCategories(data.categories || []);
      }
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  const fetchJobs = async () => {
    try {
      const response = await fetch('/api/admin/documents/jobs');
      if (response.ok) {
        const data = await response.json();
        setActiveJobs(data);
      }
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    }
  };

  useEffect(() => {
    fetchDocuments();
    fetchStatistics();
    fetchCategories();
    fetchJobs();

    // Poll for job updates
    const interval = setInterval(() => {
      fetchJobs();
      fetchDocuments();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchDocuments]);

  useEffect(() => {
    fetchDocuments();
  }, [statusFilter, categoryFilter, searchQuery, fetchDocuments]);

  const handleUpload = async (files: FileList) => {
    setUploading(true);
    const formData = new FormData();

    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }
    formData.append('category', 'general');

    try {
      const response = await fetch('/api/admin/documents/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Upload result:', result);
        await fetchDocuments();
        await fetchStatistics();
        setShowUploader(false);
      } else {
        const error = await response.json();
        alert(`Upload failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleIngest = async (doc: Document) => {
    setIngesting(doc.id);
    try {
      const response = await fetch(`/api/admin/documents/${doc.id}/ingest`, {
        method: 'POST',
      });

      if (response.ok) {
        await fetchDocuments();
        await fetchJobs();
      } else {
        const error = await response.json();
        alert(`Ingestion failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Ingestion error:', error);
      alert('Failed to start ingestion.');
    } finally {
      setIngesting(null);
    }
  };

  const handleBatchIngest = async () => {
    try {
      const response = await fetch('/api/admin/documents/ingest/batch', {
        method: 'POST',
      });

      if (response.ok) {
        const result = await response.json();
        alert(`Started ${result.jobs.length} ingestion jobs`);
        await fetchDocuments();
        await fetchJobs();
      } else {
        const error = await response.json();
        alert(`Batch ingestion failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Batch ingestion error:', error);
      alert('Failed to start batch ingestion.');
    }
  };

  const handleDelete = async (doc: Document) => {
    try {
      const response = await fetch(`/api/admin/documents/${doc.id}?delete_pdf=true&delete_markdown=true&delete_graph_data=true`, {
        method: 'DELETE',
      });

      if (response.ok) {
        await fetchDocuments();
        await fetchStatistics();
        setDeleteTarget(null);
      } else {
        const error = await response.json();
        alert(`Delete failed: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Delete error:', error);
      alert('Delete failed. Please try again.');
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
      not_started: { color: 'bg-gray-100 text-gray-600', icon: <Clock className="h-3 w-3" />, label: 'Pending' },
      processing: { color: 'bg-blue-100 text-blue-600', icon: <Loader2 className="h-3 w-3 animate-spin" />, label: 'Processing' },
      completed: { color: 'bg-green-100 text-green-600', icon: <CheckCircle className="h-3 w-3" />, label: 'Completed' },
      failed: { color: 'bg-red-100 text-red-600', icon: <XCircle className="h-3 w-3" />, label: 'Failed' },
    };
    const badge = badges[status] || badges.not_started;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${badge.color}`}>
        {badge.icon}
        {badge.label}
      </span>
    );
  };

  const getQualityBadge = (score: number | null, level: string | null) => {
    if (score === null || level === null) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-50 text-gray-400">
          <AlertCircle className="h-3 w-3" />
          Not assessed
        </span>
      );
    }

    const badges: Record<string, { color: string; icon: React.ReactNode }> = {
      excellent: { color: 'bg-green-100 text-green-700', icon: <CheckCircle className="h-3 w-3" /> },
      good: { color: 'bg-blue-100 text-blue-700', icon: <CheckCircle className="h-3 w-3" /> },
      acceptable: { color: 'bg-yellow-100 text-yellow-700', icon: <AlertCircle className="h-3 w-3" /> },
      poor: { color: 'bg-orange-100 text-orange-700', icon: <AlertTriangle className="h-3 w-3" /> },
      critical: { color: 'bg-red-100 text-red-700', icon: <XCircle className="h-3 w-3" /> },
    };

    const badge = badges[level.toLowerCase()] || badges.acceptable;
    const scorePercent = (score * 100).toFixed(0);

    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${badge.color}`}>
        {badge.icon}
        {scorePercent}%
      </span>
    );
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Document Management</h1>
          <p className="text-gray-600 mt-1">Upload, ingest, and manage PDF documents</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => { fetchDocuments(); fetchStatistics(); }}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => setShowUploader(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Upload PDFs
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      {statistics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Card className="p-4">
            <div className="text-2xl font-bold text-gray-900">{statistics.total}</div>
            <div className="text-sm text-gray-600">Total Documents</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-green-600">{statistics.completed}</div>
            <div className="text-sm text-gray-600">Ingested</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-blue-600">{statistics.total_entities}</div>
            <div className="text-sm text-gray-600">Total Entities</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-purple-600">{statistics.total_relationships}</div>
            <div className="text-sm text-gray-600">Total Relationships</div>
          </Card>
        </div>
      )}

      {/* Active Jobs */}
      {activeJobs.length > 0 && (
        <Card className="p-4 mb-6 border-blue-200 bg-blue-50">
          <h3 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Active Ingestion Jobs
          </h3>
          <div className="space-y-2">
            {activeJobs.map((job) => (
              <div key={job.job_id} className="flex items-center justify-between bg-white rounded p-2">
                <span className="text-sm font-medium">{job.filename}</span>
                <span className="text-sm text-gray-600">{job.message}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <div className="relative flex-1 min-w-64">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <Input
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border rounded-md bg-white text-sm"
        >
          <option value="">All Status</option>
          <option value="not_started">Pending</option>
          <option value="processing">Processing</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="px-3 py-2 border rounded-md bg-white text-sm"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
        {statistics && statistics.not_started > 0 && (
          <Button variant="outline" onClick={handleBatchIngest}>
            <Play className="h-4 w-4 mr-2" />
            Ingest All Pending ({statistics.not_started})
          </Button>
        )}
      </div>

      {/* Documents Table */}
      {loading ? (
        <Card className="p-6">
          <div className="flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            <span className="ml-2 text-gray-600">Loading documents...</span>
          </div>
        </Card>
      ) : documents.length === 0 ? (
        <Card className="p-6 text-center">
          <FolderOpen className="h-12 w-12 mx-auto text-gray-400 mb-4" />
          <p className="text-gray-600">No documents found</p>
          <Button className="mt-4" onClick={() => setShowUploader(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Upload your first PDF
          </Button>
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Document</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Quality</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entities</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <FileText className="h-5 w-5 text-red-500" />
                      <div>
                        <div className="font-medium text-gray-900">{doc.filename}</div>
                        {doc.markdown_path && (
                          <div className="text-xs text-green-600">Markdown available</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-gray-100 rounded text-sm">{doc.category}</span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">{formatBytes(doc.size_bytes)}</td>
                  <td className="px-6 py-4">{getStatusBadge(doc.status)}</td>
                  <td className="px-6 py-4">{getQualityBadge(doc.quality_score, doc.quality_level)}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    <span title={`${doc.entity_count || 0} entities, ${doc.relationship_count || 0} relationships`}>
                      {doc.entity_count || 0} / {doc.relationship_count || 0}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <a
                        href={`/admin/documents/${doc.id}`}
                        className="inline-flex items-center justify-center h-8 w-8 rounded-md hover:bg-gray-100 transition-colors"
                        title="Open full detail page"
                      >
                        <ExternalLink className="h-4 w-4 text-blue-600" />
                      </a>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowDetails(doc.id)}
                        title="Quick preview"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      {(doc.status === 'not_started' || doc.status === 'failed') && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleIngest(doc)}
                          disabled={ingesting === doc.id}
                          title="Start ingestion"
                        >
                          {ingesting === doc.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Play className="h-4 w-4 text-green-600" />
                          )}
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteTarget(doc)}
                        title="Delete document"
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Upload Modal */}
      {showUploader && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Upload PDF Documents</h2>
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition cursor-pointer"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files) {
                  handleUpload(e.dataTransfer.files);
                }
              }}
              onClick={() => document.getElementById('file-input')?.click()}
            >
              <Upload className="h-12 w-12 mx-auto text-gray-400 mb-4" />
              <p className="text-gray-600">Drag and drop PDF files here, or click to browse</p>
              <input
                id="file-input"
                type="file"
                multiple
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    handleUpload(e.target.files);
                  }
                }}
              />
            </div>
            {uploading && (
              <div className="mt-4 flex items-center justify-center text-blue-600">
                <Loader2 className="h-5 w-5 animate-spin mr-2" />
                Uploading...
              </div>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" onClick={() => setShowUploader(false)}>
                Cancel
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-xl font-semibold mb-4 text-red-600">Delete Document</h2>
            <p className="text-gray-600 mb-4">
              Are you sure you want to delete <strong>{deleteTarget.filename}</strong>?
            </p>
            <div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-sm text-red-700">
              This will delete:
              <ul className="list-disc ml-4 mt-1">
                <li>The PDF file</li>
                <li>The markdown conversion (if exists)</li>
                <li>All extracted entities and relationships from the graph</li>
              </ul>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDeleteTarget(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => handleDelete(deleteTarget)}
              >
                Delete
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Details Slide-over (simplified) */}
      {showDetails && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-end z-50" onClick={() => setShowDetails(null)}>
          <Card
            className="w-full max-w-2xl h-full overflow-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <DocumentDetails
              documentId={showDetails}
              onClose={() => setShowDetails(null)}
            />
          </Card>
        </div>
      )}
    </div>
  );
}

interface QualityReport {
  overall_score: number;
  quality_level: string;
  assessed_at: string;
  scores: {
    contextual_relevancy: { precision: number; recall: number; f1: number };
    context_sufficiency: { topic_coverage: number; completeness: number };
    information_density: { facts_per_chunk: number; redundancy: number; signal_to_noise: number };
    structural_clarity: { hierarchy_score: number; section_coherence: number };
    entity_density: { entities_per_chunk: number; extraction_rate: number; consistency: number };
    chunking_quality: { self_containment: number; boundary_coherence: number; retrieval_quality: number };
  };
  recommendations: string[];
}

function DocumentDetails({ documentId, onClose }: { documentId: string; onClose: () => void }) {
  const [details, setDetails] = useState<any>(null);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState(false);
  const [activeTab, setActiveTab] = useState<'info' | 'quality' | 'preview'>('info');

  const fetchDetails = async () => {
    try {
      const response = await fetch(`/api/admin/documents/${documentId}`);
      if (response.ok) {
        const data = await response.json();
        setDetails(data);
      }
    } catch (err) {
      console.error('Failed to load details:', err);
    }
  };

  const fetchQuality = async () => {
    try {
      const response = await fetch(`/api/admin/documents/${documentId}/quality`);
      if (response.ok) {
        const data = await response.json();
        if (data.overall_score !== undefined) {
          setQuality(data);
        }
      }
    } catch (err) {
      console.error('Failed to load quality:', err);
    }
  };

  useEffect(() => {
    Promise.all([fetchDetails(), fetchQuality()]).finally(() => setLoading(false));
  }, [documentId]);

  const handleAssessQuality = async () => {
    setAssessing(true);
    try {
      const response = await fetch(`/api/admin/documents/${documentId}/quality/assess`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        setQuality(data);
        setActiveTab('quality');
      } else {
        const err = await response.json();
        alert(`Assessment failed: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Quality assessment failed:', err);
      alert('Failed to assess quality');
    } finally {
      setAssessing(false);
    }
  };

  const getQualityLevelColor = (level: string) => {
    const colors: Record<string, string> = {
      excellent: 'text-green-700 bg-green-100',
      good: 'text-blue-700 bg-blue-100',
      acceptable: 'text-yellow-700 bg-yellow-100',
      poor: 'text-orange-700 bg-orange-100',
      critical: 'text-red-700 bg-red-100',
    };
    return colors[level?.toLowerCase()] || 'text-gray-600 bg-gray-100';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  if (!details) {
    return <div>Document not found</div>;
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold truncate">{details.filename}</h2>
        <Button variant="ghost" onClick={onClose}>Close</Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b mb-4">
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'info' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('info')}
        >
          Info
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'quality' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('quality')}
        >
          Quality
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'preview' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => setActiveTab('preview')}
        >
          Preview
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        {/* Info Tab */}
        {activeTab === 'info' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm text-gray-500">Category</div>
                <div className="font-medium">{details.category}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Status</div>
                <div className="font-medium">{details.status}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Entities</div>
                <div className="font-medium">{details.entity_count || 0}</div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Relationships</div>
                <div className="font-medium">{details.relationship_count || 0}</div>
              </div>
            </div>

            {details.error_message && (
              <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
                <strong>Error:</strong> {details.error_message}
              </div>
            )}
          </div>
        )}

        {/* Quality Tab */}
        {activeTab === 'quality' && (
          <div className="space-y-4">
            {quality ? (
              <>
                {/* Quality Summary */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getQualityLevelColor(quality.quality_level)}`}>
                      {quality.quality_level.toUpperCase()}
                    </span>
                    <span className="text-lg font-bold">{(quality.overall_score * 100).toFixed(0)}%</span>
                  </div>
                  <Button variant="outline" size="sm" onClick={handleAssessQuality} disabled={assessing}>
                    {assessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                    <span className="ml-2">Re-assess</span>
                  </Button>
                </div>

                {/* Metric Categories */}
                <div className="space-y-3">
                  <QualityMetricGroup
                    title="Contextual Relevancy"
                    metrics={[
                      { label: 'Precision', value: quality.scores.contextual_relevancy.precision },
                      { label: 'Recall', value: quality.scores.contextual_relevancy.recall },
                      { label: 'F1 Score', value: quality.scores.contextual_relevancy.f1 },
                    ]}
                  />
                  <QualityMetricGroup
                    title="Context Sufficiency"
                    metrics={[
                      { label: 'Topic Coverage', value: quality.scores.context_sufficiency.topic_coverage },
                      { label: 'Completeness', value: quality.scores.context_sufficiency.completeness },
                    ]}
                  />
                  <QualityMetricGroup
                    title="Information Density"
                    metrics={[
                      { label: 'Signal/Noise', value: quality.scores.information_density.signal_to_noise },
                      { label: 'Redundancy', value: 1 - quality.scores.information_density.redundancy },
                    ]}
                  />
                  <QualityMetricGroup
                    title="Structure & Entities"
                    metrics={[
                      { label: 'Hierarchy', value: quality.scores.structural_clarity.hierarchy_score },
                      { label: 'Entity Extraction', value: quality.scores.entity_density.extraction_rate },
                    ]}
                  />
                  <QualityMetricGroup
                    title="Chunking Quality"
                    metrics={[
                      { label: 'Boundary Coherence', value: quality.scores.chunking_quality.boundary_coherence },
                      { label: 'Retrieval Quality', value: quality.scores.chunking_quality.retrieval_quality },
                    ]}
                  />
                </div>

                {/* Recommendations */}
                {quality.recommendations.length > 0 && (
                  <div className="pt-4 border-t">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">Recommendations</h4>
                    <ul className="space-y-2">
                      {quality.recommendations.map((rec, i) => (
                        <li key={i} className="text-sm text-gray-600 bg-yellow-50 px-3 py-2 rounded border border-yellow-100">
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="text-xs text-gray-400 pt-2">
                  Assessed: {new Date(quality.assessed_at).toLocaleString()}
                </div>
              </>
            ) : (
              <div className="text-center py-12">
                <BarChart3 className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500 mb-4">No quality assessment yet</p>
                <Button onClick={handleAssessQuality} disabled={assessing || details.status !== 'completed'}>
                  {assessing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Assessing...
                    </>
                  ) : (
                    <>
                      <BarChart3 className="h-4 w-4 mr-2" />
                      Assess Quality
                    </>
                  )}
                </Button>
                {details.status !== 'completed' && (
                  <p className="text-sm text-gray-400 mt-2">Document must be ingested first</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Preview Tab */}
        {activeTab === 'preview' && (
          <div>
            {details.markdown_preview ? (
              <>
                <div className="bg-gray-50 border rounded p-4 max-h-[60vh] overflow-auto">
                  <pre className="text-sm whitespace-pre-wrap font-mono">{details.markdown_preview}</pre>
                </div>
                {details.markdown_length > 2000 && (
                  <p className="text-xs text-gray-500 mt-2">
                    Showing first 2000 characters of {details.markdown_length.toLocaleString()} total
                  </p>
                )}
              </>
            ) : (
              <div className="text-center py-12">
                <FileText className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">No markdown preview available</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function QualityMetricGroup({ title, metrics }: { title: string; metrics: { label: string; value: number }[] }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">{title}</h4>
      <div className="grid grid-cols-2 gap-2">
        {metrics.map((m, i) => (
          <div key={i}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-600">{m.label}</span>
              <span className="font-medium">{(m.value * 100).toFixed(0)}%</span>
            </div>
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${
                  m.value >= 0.8 ? 'bg-green-500' :
                  m.value >= 0.6 ? 'bg-blue-500' :
                  m.value >= 0.4 ? 'bg-yellow-500' :
                  'bg-red-500'
                }`}
                style={{ width: `${Math.min(m.value * 100, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
