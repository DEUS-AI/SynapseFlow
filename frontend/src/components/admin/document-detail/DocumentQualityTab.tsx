import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle, BarChart3, RefreshCw, Lightbulb } from 'lucide-react';
import { DocumentQualityRadar } from '../../charts/MetricRadarChart';
import { RatingBar } from '../../feedback/RatingVisualization';

interface DocumentQualityTabProps {
  docId: string;
}

interface QualityMetrics {
  overall_score: number;
  quality_level: string;
  contextual_relevancy?: {
    score: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
  };
  context_sufficiency?: {
    score: number;
    topic_coverage?: number;
    completeness?: number;
  };
  information_density?: {
    score: number;
    facts_per_chunk?: number;
    redundancy_ratio?: number;
    signal_to_noise?: number;
  };
  structural_clarity?: {
    score: number;
    hierarchy_score?: number;
    section_coherence?: number;
  };
  entity_density?: {
    score: number;
    entities_per_chunk?: number;
    extraction_rate?: number;
    consistency?: number;
  };
  chunking_quality?: {
    score: number;
    self_containment?: number;
    boundary_coherence?: number;
    retrieval_quality?: number;
  };
  recommendations?: string[];
  assessed_at?: string;
}

export function DocumentQualityTab({ docId }: DocumentQualityTabProps) {
  const [quality, setQuality] = useState<QualityMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadQuality = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/admin/documents/${docId}/quality`);
      if (!response.ok) {
        if (response.status === 404) {
          setQuality(null);
          return;
        }
        throw new Error('Failed to load quality metrics');
      }

      const data = await response.json();
      setQuality(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load quality');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQuality();
  }, [docId]);

  const runAssessment = async () => {
    try {
      setAssessing(true);
      setError(null);

      const response = await fetch(`/api/admin/documents/${docId}/quality/assess`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to run assessment');
      }

      const data = await response.json();
      setQuality(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed');
    } finally {
      setAssessing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <p className="text-slate-400">Loading quality metrics...</p>
        </div>
      </div>
    );
  }

  if (!quality) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4 text-center">
          <BarChart3 className="w-12 h-12 text-slate-600" />
          <div>
            <h3 className="text-lg font-medium text-slate-200">No Quality Assessment</h3>
            <p className="text-slate-400 mt-2">
              This document hasn't been assessed for quality yet.
            </p>
          </div>
          <button
            onClick={runAssessment}
            disabled={assessing}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            {assessing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <BarChart3 className="w-4 h-4" />
            )}
            Run Quality Assessment
          </button>
        </div>
      </div>
    );
  }

  const qualityColor =
    quality.quality_level === 'excellent' ? 'text-green-400' :
    quality.quality_level === 'good' ? 'text-blue-400' :
    quality.quality_level === 'acceptable' ? 'text-yellow-400' :
    quality.quality_level === 'poor' ? 'text-orange-400' :
    'text-red-400';

  // Prepare radar data
  const radarMetrics = {
    contextualRelevancy: quality.contextual_relevancy?.score ?? 0,
    contextSufficiency: quality.context_sufficiency?.score ?? 0,
    informationDensity: quality.information_density?.score ?? 0,
    structuralClarity: quality.structural_clarity?.score ?? 0,
    entityDensity: quality.entity_density?.score ?? 0,
    chunkingQuality: quality.chunking_quality?.score ?? 0,
  };

  return (
    <div className="space-y-6">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-slate-200">Quality Assessment</h2>
          {quality.assessed_at && (
            <p className="text-sm text-slate-400 mt-1">
              Last assessed: {new Date(quality.assessed_at).toLocaleString()}
            </p>
          )}
        </div>
        <button
          onClick={runAssessment}
          disabled={assessing}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:cursor-not-allowed text-slate-200 rounded-lg transition-colors text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${assessing ? 'animate-spin' : ''}`} />
          Re-assess
        </button>
      </div>

      {/* Overall score and radar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Overall score */}
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700 flex flex-col items-center justify-center">
          <div className={`text-5xl font-bold ${qualityColor}`}>
            {(quality.overall_score * 100).toFixed(0)}%
          </div>
          <div className={`text-lg ${qualityColor} mt-2 capitalize`}>
            {quality.quality_level}
          </div>
          <div className="w-full mt-4">
            <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  quality.quality_level === 'excellent' ? 'bg-green-500' :
                  quality.quality_level === 'good' ? 'bg-blue-500' :
                  quality.quality_level === 'acceptable' ? 'bg-yellow-500' :
                  quality.quality_level === 'poor' ? 'bg-orange-500' :
                  'bg-red-500'
                }`}
                style={{ width: `${quality.overall_score * 100}%` }}
              />
            </div>
          </div>
        </div>

        {/* Radar chart */}
        <div className="lg:col-span-2 bg-slate-800/50 rounded-lg p-6 border border-slate-700">
          <DocumentQualityRadar metrics={radarMetrics} height={250} />
        </div>
      </div>

      {/* Detailed metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {quality.contextual_relevancy && (
          <MetricCard
            title="Contextual Relevancy"
            score={quality.contextual_relevancy.score}
            details={[
              { label: 'Precision', value: quality.contextual_relevancy.precision },
              { label: 'Recall', value: quality.contextual_relevancy.recall },
              { label: 'F1 Score', value: quality.contextual_relevancy.f1_score },
            ]}
          />
        )}
        {quality.context_sufficiency && (
          <MetricCard
            title="Context Sufficiency"
            score={quality.context_sufficiency.score}
            details={[
              { label: 'Topic Coverage', value: quality.context_sufficiency.topic_coverage },
              { label: 'Completeness', value: quality.context_sufficiency.completeness },
            ]}
          />
        )}
        {quality.information_density && (
          <MetricCard
            title="Information Density"
            score={quality.information_density.score}
            details={[
              { label: 'Facts/Chunk', value: quality.information_density.facts_per_chunk, format: 'number' },
              { label: 'Redundancy', value: quality.information_density.redundancy_ratio },
              { label: 'Signal/Noise', value: quality.information_density.signal_to_noise },
            ]}
          />
        )}
        {quality.structural_clarity && (
          <MetricCard
            title="Structural Clarity"
            score={quality.structural_clarity.score}
            details={[
              { label: 'Hierarchy', value: quality.structural_clarity.hierarchy_score },
              { label: 'Coherence', value: quality.structural_clarity.section_coherence },
            ]}
          />
        )}
        {quality.entity_density && (
          <MetricCard
            title="Entity Density"
            score={quality.entity_density.score}
            details={[
              { label: 'Entities/Chunk', value: quality.entity_density.entities_per_chunk, format: 'number' },
              { label: 'Extraction Rate', value: quality.entity_density.extraction_rate },
              { label: 'Consistency', value: quality.entity_density.consistency },
            ]}
          />
        )}
        {quality.chunking_quality && (
          <MetricCard
            title="Chunking Quality"
            score={quality.chunking_quality.score}
            details={[
              { label: 'Self-Containment', value: quality.chunking_quality.self_containment },
              { label: 'Boundary Coherence', value: quality.chunking_quality.boundary_coherence },
              { label: 'Retrieval Quality', value: quality.chunking_quality.retrieval_quality },
            ]}
          />
        )}
      </div>

      {/* Recommendations */}
      {quality.recommendations && quality.recommendations.length > 0 && (
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
          <h3 className="text-lg font-medium text-slate-200 mb-4 flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-yellow-400" />
            Recommendations
          </h3>
          <ul className="space-y-2">
            {quality.recommendations.map((rec, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-slate-300">
                <span className="text-yellow-400 mt-0.5">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// Metric card component
interface MetricCardProps {
  title: string;
  score: number;
  details: { label: string; value?: number; format?: 'percent' | 'number' }[];
}

function MetricCard({ title, score, details }: MetricCardProps) {
  return (
    <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium text-slate-200">{title}</h4>
        <span className={`text-lg font-bold ${
          score >= 0.8 ? 'text-green-400' :
          score >= 0.6 ? 'text-blue-400' :
          score >= 0.4 ? 'text-yellow-400' :
          'text-red-400'
        }`}>
          {(score * 100).toFixed(0)}%
        </span>
      </div>
      <RatingBar rating={score} showPercentage={false} />
      {details.some(d => d.value !== undefined) && (
        <div className="mt-3 space-y-1.5">
          {details.filter(d => d.value !== undefined).map((detail, i) => (
            <div key={i} className="flex justify-between text-xs">
              <span className="text-slate-400">{detail.label}</span>
              <span className="text-slate-300">
                {detail.format === 'number'
                  ? detail.value!.toFixed(1)
                  : `${(detail.value! * 100).toFixed(0)}%`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
