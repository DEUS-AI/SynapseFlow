import React, { useState, useEffect } from 'react';
import {
  BarChart3, FileCheck, GitBranch, AlertTriangle,
  CheckCircle, XCircle, AlertCircle, TrendingUp,
  RefreshCw, Loader2, ChevronRight, Database, Clock,
  Activity, Play, Pause
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card } from '../ui/card';

interface TrendDataPoint {
  date: string;
  score: number;
  count?: number;
}

interface DocumentTrends {
  period_days: number;
  data_points: TrendDataPoint[];
  total_assessments: number;
  trend_direction: 'improving' | 'stable' | 'declining';
  average_change: number;
}

interface OntologyTrends {
  period_days: number;
  data_points: TrendDataPoint[];
  total_assessments: number;
  trend_direction: 'improving' | 'stable' | 'declining';
  average_change: number;
}

interface ScannerStatus {
  enabled: boolean;
  running: boolean;
  last_document_scan?: string;
  last_ontology_scan?: string;
  documents_scanned_total: number;
  ontology_scans_total: number;
  scan_interval_seconds: number;
}

interface DocumentQualityStats {
  total_assessed: number;
  by_quality_level: Record<string, number>;
  averages: {
    overall_score: number;
    context_precision: number;
    context_recall: number;
    topic_coverage: number;
    signal_to_noise: number;
    entity_extraction_rate: number;
    retrieval_quality: number;
  };
}

interface OntologyQualityStats {
  has_assessment: boolean;
  total_assessments?: number;
  latest?: {
    assessment_id: string;
    overall_score: number;
    quality_level: string;
    coverage_ratio: number;
    compliance_ratio: number;
    coherence_ratio: number;
    consistency_ratio: number;
    entity_count: number;
    relationship_count: number;
    orphan_nodes: number;
    critical_issues: string[];
    recommendations: string[];
    assessed_at: string;
  };
  by_quality_level?: Record<string, number>;
}

interface QualityDashboardProps {
  onNavigateToDocuments?: () => void;
}

export function QualityDashboard({ onNavigateToDocuments }: QualityDashboardProps) {
  const [documentStats, setDocumentStats] = useState<DocumentQualityStats | null>(null);
  const [ontologyStats, setOntologyStats] = useState<OntologyQualityStats | null>(null);
  const [documentTrends, setDocumentTrends] = useState<DocumentTrends | null>(null);
  const [ontologyTrends, setOntologyTrends] = useState<OntologyTrends | null>(null);
  const [scannerStatus, setScannerStatus] = useState<ScannerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState<'document' | 'ontology' | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'trends' | 'scanner'>('overview');

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const [docResponse, ontResponse, docTrendsResponse, ontTrendsResponse, scannerResponse] = await Promise.all([
        fetch('/api/admin/documents/quality/summary'),
        fetch('/api/ontology/quality'),
        fetch('/api/quality/trends/documents?days=30'),
        fetch('/api/quality/trends/ontology?days=30'),
        fetch('/api/quality/scanner/status'),
      ]);

      if (docResponse.ok) {
        const docData = await docResponse.json();
        setDocumentStats(docData);
      }

      if (ontResponse.ok) {
        const ontData = await ontResponse.json();
        setOntologyStats(ontData);
      }

      if (docTrendsResponse.ok) {
        const trendsData = await docTrendsResponse.json();
        setDocumentTrends(trendsData);
      }

      if (ontTrendsResponse.ok) {
        const trendsData = await ontTrendsResponse.json();
        setOntologyTrends(trendsData);
      }

      if (scannerResponse.ok) {
        const scannerData = await scannerResponse.json();
        setScannerStatus(scannerData);
      }
    } catch (err) {
      console.error('Failed to fetch quality stats:', err);
      setError('Failed to load quality metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleAssessOntology = async () => {
    setAssessing('ontology');
    try {
      const response = await fetch('/api/ontology/quality/assess', {
        method: 'POST',
      });
      if (response.ok) {
        await fetchStats();
      } else {
        const err = await response.json();
        alert(`Assessment failed: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Ontology assessment failed:', err);
      alert('Failed to assess ontology quality');
    } finally {
      setAssessing(null);
    }
  };

  const handleManualScan = async (scanType: 'documents' | 'ontology' | 'both') => {
    setScanning(true);
    try {
      const response = await fetch(`/api/quality/scanner/scan?scan_type=${scanType}`, {
        method: 'POST',
      });
      if (response.ok) {
        await fetchStats();
      } else {
        const err = await response.json();
        alert(`Scan failed: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Manual scan failed:', err);
      alert('Failed to run manual scan');
    } finally {
      setScanning(false);
    }
  };

  const getTrendIcon = (direction: string) => {
    if (direction === 'improving') return <TrendingUp className="h-4 w-4 text-green-500" />;
    if (direction === 'declining') return <TrendingUp className="h-4 w-4 text-red-500 rotate-180" />;
    return <Activity className="h-4 w-4 text-gray-500" />;
  };

  const getTrendColor = (direction: string) => {
    if (direction === 'improving') return 'text-green-600';
    if (direction === 'declining') return 'text-red-600';
    return 'text-gray-600';
  };

  const getQualityLevelColor = (level: string) => {
    const colors: Record<string, string> = {
      excellent: 'text-green-600 bg-green-100',
      good: 'text-blue-600 bg-blue-100',
      acceptable: 'text-yellow-600 bg-yellow-100',
      poor: 'text-orange-600 bg-orange-100',
      critical: 'text-red-600 bg-red-100',
    };
    return colors[level?.toLowerCase()] || 'text-gray-600 bg-gray-100';
  };

  const getQualityLevelIcon = (level: string) => {
    const icons: Record<string, React.ReactNode> = {
      excellent: <CheckCircle className="h-5 w-5 text-green-600" />,
      good: <CheckCircle className="h-5 w-5 text-blue-600" />,
      acceptable: <AlertCircle className="h-5 w-5 text-yellow-600" />,
      poor: <AlertTriangle className="h-5 w-5 text-orange-600" />,
      critical: <XCircle className="h-5 w-5 text-red-600" />,
    };
    return icons[level?.toLowerCase()] || <AlertCircle className="h-5 w-5 text-gray-600" />;
  };

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatScore = (value: number) => {
    return value.toFixed(2);
  };

  if (loading) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-3 text-gray-600">Loading quality metrics...</span>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="text-center py-12">
          <AlertTriangle className="h-12 w-12 mx-auto text-red-400 mb-4" />
          <p className="text-red-600">{error}</p>
          <Button variant="outline" className="mt-4" onClick={fetchStats}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Quality Metrics</h2>
          <p className="text-gray-400 mt-1">Document and ontology quality assessments</p>
        </div>
        <Button variant="outline" onClick={fetchStats}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-700 pb-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${
            activeTab === 'overview'
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('trends')}
          className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${
            activeTab === 'trends'
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          <TrendingUp className="h-4 w-4 inline mr-2" />
          Trends
        </button>
        <button
          onClick={() => setActiveTab('scanner')}
          className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${
            activeTab === 'scanner'
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          <Activity className="h-4 w-4 inline mr-2" />
          Scanner
        </button>
      </div>

      {activeTab === 'trends' && (
        <TrendsView
          documentTrends={documentTrends}
          ontologyTrends={ontologyTrends}
          getTrendIcon={getTrendIcon}
          getTrendColor={getTrendColor}
        />
      )}

      {activeTab === 'scanner' && (
        <ScannerView
          scannerStatus={scannerStatus}
          scanning={scanning}
          onManualScan={handleManualScan}
        />
      )}

      {activeTab !== 'overview' ? null : (
        <>
          {/* Summary Cards - Only show in overview */}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-50 rounded-lg">
              <FileCheck className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Documents Assessed</p>
              <p className="text-2xl font-bold">{documentStats?.total_assessed || 0}</p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-50 rounded-lg">
              <TrendingUp className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Avg Document Score</p>
              <p className="text-2xl font-bold">
                {formatScore(documentStats?.averages?.overall_score || 0)}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-50 rounded-lg">
              <GitBranch className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Ontology Score</p>
              <p className="text-2xl font-bold">
                {ontologyStats?.latest
                  ? formatScore(ontologyStats.latest.overall_score)
                  : 'N/A'}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-50 rounded-lg">
              <Database className="h-6 w-6 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Graph Entities</p>
              <p className="text-2xl font-bold">
                {ontologyStats?.latest?.entity_count?.toLocaleString() || 0}
              </p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Quality Card */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-blue-600" />
              Document Quality
            </h3>
            {onNavigateToDocuments && (
              <Button variant="ghost" size="sm" onClick={onNavigateToDocuments}>
                View Documents
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            )}
          </div>

          {documentStats && documentStats.total_assessed > 0 ? (
            <div className="space-y-4">
              {/* Quality Level Distribution */}
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Quality Distribution</p>
                <div className="flex gap-2 flex-wrap">
                  {['excellent', 'good', 'acceptable', 'poor', 'critical'].map((level) => {
                    const count = documentStats.by_quality_level[level] || 0;
                    if (count === 0) return null;
                    return (
                      <span
                        key={level}
                        className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${getQualityLevelColor(level)}`}
                      >
                        {getQualityLevelIcon(level)}
                        {level.charAt(0).toUpperCase() + level.slice(1)}: {count}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Average Metrics */}
              <div className="pt-4 border-t">
                <p className="text-sm font-medium text-gray-700 mb-3">Average Scores</p>
                <div className="grid grid-cols-2 gap-3">
                  <MetricBar
                    label="Context Precision"
                    value={documentStats.averages.context_precision}
                  />
                  <MetricBar
                    label="Context Recall"
                    value={documentStats.averages.context_recall}
                  />
                  <MetricBar
                    label="Topic Coverage"
                    value={documentStats.averages.topic_coverage}
                  />
                  <MetricBar
                    label="Signal/Noise"
                    value={documentStats.averages.signal_to_noise}
                  />
                  <MetricBar
                    label="Entity Extraction"
                    value={documentStats.averages.entity_extraction_rate}
                  />
                  <MetricBar
                    label="Retrieval Quality"
                    value={documentStats.averages.retrieval_quality}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <FileCheck className="h-12 w-12 mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500">No documents assessed yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Assess documents from the Documents page
              </p>
            </div>
          )}
        </Card>

        {/* Ontology Quality Card */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-purple-600" />
              Ontology Quality
            </h3>
            <Button
              variant="outline"
              size="sm"
              onClick={handleAssessOntology}
              disabled={assessing === 'ontology'}
            >
              {assessing === 'ontology' ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Assessing...
                </>
              ) : (
                <>
                  <BarChart3 className="h-4 w-4 mr-2" />
                  Run Assessment
                </>
              )}
            </Button>
          </div>

          {ontologyStats?.has_assessment && ontologyStats.latest ? (
            <div className="space-y-4">
              {/* Quality Level Badge */}
              <div className="flex items-center gap-3">
                <span
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold ${getQualityLevelColor(ontologyStats.latest.quality_level)}`}
                >
                  {getQualityLevelIcon(ontologyStats.latest.quality_level)}
                  {ontologyStats.latest.quality_level.toUpperCase()}
                </span>
                <span className="text-sm text-gray-500">
                  Score: {formatScore(ontologyStats.latest.overall_score)}
                </span>
              </div>

              {/* Key Metrics */}
              <div className="grid grid-cols-2 gap-3">
                <MetricBar
                  label="Coverage"
                  value={ontologyStats.latest.coverage_ratio}
                />
                <MetricBar
                  label="Compliance"
                  value={ontologyStats.latest.compliance_ratio}
                />
                <MetricBar
                  label="Coherence"
                  value={ontologyStats.latest.coherence_ratio}
                />
                <MetricBar
                  label="Consistency"
                  value={ontologyStats.latest.consistency_ratio}
                />
              </div>

              {/* Stats */}
              <div className="pt-4 border-t grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    {ontologyStats.latest.entity_count.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500">Entities</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    {ontologyStats.latest.relationship_count.toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500">Relationships</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-orange-600">
                    {ontologyStats.latest.orphan_nodes}
                  </p>
                  <p className="text-xs text-gray-500">Orphan Nodes</p>
                </div>
              </div>

              {/* Critical Issues */}
              {ontologyStats.latest.critical_issues.length > 0 && (
                <div className="pt-4 border-t">
                  <p className="text-sm font-medium text-red-700 mb-2 flex items-center gap-1">
                    <AlertTriangle className="h-4 w-4" />
                    Critical Issues
                  </p>
                  <ul className="space-y-1">
                    {ontologyStats.latest.critical_issues.slice(0, 3).map((issue, i) => (
                      <li key={i} className="text-sm text-red-600 bg-red-50 px-3 py-1 rounded">
                        {issue}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Recommendations */}
              {ontologyStats.latest.recommendations.length > 0 && (
                <div className="pt-4 border-t">
                  <p className="text-sm font-medium text-gray-700 mb-2">Top Recommendations</p>
                  <ul className="space-y-1">
                    {ontologyStats.latest.recommendations.slice(0, 3).map((rec, i) => (
                      <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                        <ChevronRight className="h-4 w-4 text-gray-400 flex-shrink-0 mt-0.5" />
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Last Assessment */}
              <div className="pt-4 border-t text-xs text-gray-400">
                Last assessed: {new Date(ontologyStats.latest.assessed_at).toLocaleString()}
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <GitBranch className="h-12 w-12 mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500">No ontology assessment yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Click "Run Assessment" to analyze the knowledge graph
              </p>
            </div>
          )}
        </Card>
      </div>
        </>
      )}
    </div>
  );
}

// Trends View Component
interface TrendsViewProps {
  documentTrends: DocumentTrends | null;
  ontologyTrends: OntologyTrends | null;
  getTrendIcon: (direction: string) => React.ReactNode;
  getTrendColor: (direction: string) => string;
}

function TrendsView({ documentTrends, ontologyTrends, getTrendIcon, getTrendColor }: TrendsViewProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Quality Trends */}
        <Card className="p-6 bg-slate-800 border-slate-700">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <FileCheck className="h-5 w-5 text-blue-500" />
            Document Quality Trends
          </h3>
          {documentTrends && documentTrends.data_points.length > 0 ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getTrendIcon(documentTrends.trend_direction)}
                  <span className={`font-medium ${getTrendColor(documentTrends.trend_direction)}`}>
                    {documentTrends.trend_direction.charAt(0).toUpperCase() + documentTrends.trend_direction.slice(1)}
                  </span>
                </div>
                <span className="text-sm text-gray-400">
                  {documentTrends.total_assessments} assessments in {documentTrends.period_days} days
                </span>
              </div>

              <TrendChart dataPoints={documentTrends.data_points} color="blue" />

              <div className="text-sm text-gray-400">
                Average change: {documentTrends.average_change >= 0 ? '+' : ''}{(documentTrends.average_change * 100).toFixed(1)}%
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <TrendingUp className="h-12 w-12 mx-auto text-gray-600 mb-3" />
              <p className="text-gray-400">No trend data available yet</p>
              <p className="text-sm text-gray-500 mt-1">
                Assess more documents to see trends
              </p>
            </div>
          )}
        </Card>

        {/* Ontology Quality Trends */}
        <Card className="p-6 bg-slate-800 border-slate-700">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <GitBranch className="h-5 w-5 text-purple-500" />
            Ontology Quality Trends
          </h3>
          {ontologyTrends && ontologyTrends.data_points.length > 0 ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getTrendIcon(ontologyTrends.trend_direction)}
                  <span className={`font-medium ${getTrendColor(ontologyTrends.trend_direction)}`}>
                    {ontologyTrends.trend_direction.charAt(0).toUpperCase() + ontologyTrends.trend_direction.slice(1)}
                  </span>
                </div>
                <span className="text-sm text-gray-400">
                  {ontologyTrends.total_assessments} assessments in {ontologyTrends.period_days} days
                </span>
              </div>

              <TrendChart dataPoints={ontologyTrends.data_points} color="purple" />

              <div className="text-sm text-gray-400">
                Average change: {ontologyTrends.average_change >= 0 ? '+' : ''}{(ontologyTrends.average_change * 100).toFixed(1)}%
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <TrendingUp className="h-12 w-12 mx-auto text-gray-600 mb-3" />
              <p className="text-gray-400">No trend data available yet</p>
              <p className="text-sm text-gray-500 mt-1">
                Run ontology assessments to see trends
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// Simple Trend Chart Component
interface TrendChartProps {
  dataPoints: TrendDataPoint[];
  color: 'blue' | 'purple' | 'green';
}

function TrendChart({ dataPoints, color }: TrendChartProps) {
  const maxScore = Math.max(...dataPoints.map(p => p.score), 1);
  const minScore = Math.min(...dataPoints.map(p => p.score), 0);
  const range = maxScore - minScore || 1;

  const colorClasses = {
    blue: { bg: 'bg-blue-500', line: 'border-blue-500', fill: 'bg-blue-500/20' },
    purple: { bg: 'bg-purple-500', line: 'border-purple-500', fill: 'bg-purple-500/20' },
    green: { bg: 'bg-green-500', line: 'border-green-500', fill: 'bg-green-500/20' },
  };

  const colors = colorClasses[color];

  return (
    <div className="relative h-40 bg-slate-900 rounded-lg p-4">
      {/* Y-axis labels */}
      <div className="absolute left-0 top-4 bottom-4 w-10 flex flex-col justify-between text-xs text-gray-500">
        <span>{(maxScore * 100).toFixed(0)}%</span>
        <span>{((maxScore + minScore) / 2 * 100).toFixed(0)}%</span>
        <span>{(minScore * 100).toFixed(0)}%</span>
      </div>

      {/* Chart area */}
      <div className="ml-12 h-full flex items-end gap-1">
        {dataPoints.slice(-14).map((point, index) => {
          const height = ((point.score - minScore) / range) * 100;
          return (
            <div
              key={index}
              className="flex-1 flex flex-col items-center group relative"
            >
              <div
                className={`w-full ${colors.bg} rounded-t opacity-80 hover:opacity-100 transition-opacity`}
                style={{ height: `${height}%`, minHeight: '4px' }}
              />
              {/* Tooltip */}
              <div className="absolute bottom-full mb-2 hidden group-hover:block bg-slate-700 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                {new Date(point.date).toLocaleDateString()}: {(point.score * 100).toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>

      {/* X-axis labels */}
      <div className="ml-12 flex justify-between text-xs text-gray-500 mt-2">
        {dataPoints.length > 0 && (
          <>
            <span>{new Date(dataPoints[0].date).toLocaleDateString('en', { month: 'short', day: 'numeric' })}</span>
            <span>{new Date(dataPoints[dataPoints.length - 1].date).toLocaleDateString('en', { month: 'short', day: 'numeric' })}</span>
          </>
        )}
      </div>
    </div>
  );
}

// Scanner View Component
interface ScannerViewProps {
  scannerStatus: ScannerStatus | null;
  scanning: boolean;
  onManualScan: (type: 'documents' | 'ontology' | 'both') => void;
}

function ScannerView({ scannerStatus, scanning, onManualScan }: ScannerViewProps) {
  return (
    <div className="space-y-6">
      <Card className="p-6 bg-slate-800 border-slate-700">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
          <Activity className="h-5 w-5 text-green-500" />
          Quality Scanner Status
        </h3>

        {scannerStatus ? (
          <div className="space-y-6">
            {/* Status Badge */}
            <div className="flex items-center gap-4">
              <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                scannerStatus.running
                  ? 'bg-green-900/50 text-green-400'
                  : scannerStatus.enabled
                    ? 'bg-yellow-900/50 text-yellow-400'
                    : 'bg-gray-700 text-gray-400'
              }`}>
                {scannerStatus.running ? (
                  <><Play className="h-4 w-4" /> Running</>
                ) : scannerStatus.enabled ? (
                  <><Pause className="h-4 w-4" /> Enabled (Idle)</>
                ) : (
                  <><Pause className="h-4 w-4" /> Disabled</>
                )}
              </div>
              <span className="text-sm text-gray-400">
                Scan interval: {Math.round(scannerStatus.scan_interval_seconds / 60)} minutes
              </span>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-900 rounded-lg p-4">
                <p className="text-sm text-gray-400">Documents Scanned</p>
                <p className="text-2xl font-bold text-white">{scannerStatus.documents_scanned_total}</p>
              </div>
              <div className="bg-slate-900 rounded-lg p-4">
                <p className="text-sm text-gray-400">Ontology Scans</p>
                <p className="text-2xl font-bold text-white">{scannerStatus.ontology_scans_total}</p>
              </div>
              <div className="bg-slate-900 rounded-lg p-4">
                <p className="text-sm text-gray-400">Last Document Scan</p>
                <p className="text-sm text-white">
                  {scannerStatus.last_document_scan
                    ? new Date(scannerStatus.last_document_scan).toLocaleString()
                    : 'Never'}
                </p>
              </div>
              <div className="bg-slate-900 rounded-lg p-4">
                <p className="text-sm text-gray-400">Last Ontology Scan</p>
                <p className="text-sm text-white">
                  {scannerStatus.last_ontology_scan
                    ? new Date(scannerStatus.last_ontology_scan).toLocaleString()
                    : 'Never'}
                </p>
              </div>
            </div>

            {/* Manual Scan Buttons */}
            <div className="border-t border-slate-700 pt-4">
              <p className="text-sm font-medium text-gray-300 mb-3">Run Manual Scan</p>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => onManualScan('documents')}
                  disabled={scanning}
                  className="flex-1"
                >
                  {scanning ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <FileCheck className="h-4 w-4 mr-2" />
                  )}
                  Scan Documents
                </Button>
                <Button
                  variant="outline"
                  onClick={() => onManualScan('ontology')}
                  disabled={scanning}
                  className="flex-1"
                >
                  {scanning ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <GitBranch className="h-4 w-4 mr-2" />
                  )}
                  Scan Ontology
                </Button>
                <Button
                  onClick={() => onManualScan('both')}
                  disabled={scanning}
                  className="flex-1 bg-blue-600 hover:bg-blue-700"
                >
                  {scanning ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Activity className="h-4 w-4 mr-2" />
                  )}
                  Scan Both
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <Activity className="h-12 w-12 mx-auto text-gray-600 mb-3" />
            <p className="text-gray-400">Scanner status unavailable</p>
            <p className="text-sm text-gray-500 mt-1">
              Check if the quality scanner job is configured
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}

interface MetricBarProps {
  label: string;
  value: number;
}

function MetricBar({ label, value }: MetricBarProps) {
  const percentage = Math.min(value * 100, 100);
  const getColor = () => {
    if (percentage >= 80) return 'bg-green-500';
    if (percentage >= 60) return 'bg-blue-500';
    if (percentage >= 40) return 'bg-yellow-500';
    if (percentage >= 20) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium">{percentage.toFixed(0)}%</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor()} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export default QualityDashboard;
