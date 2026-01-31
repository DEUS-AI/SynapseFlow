import React, { useState, useEffect } from 'react';

interface FeedbackStats {
  total_feedbacks: number;
  positive_feedbacks: number;
  negative_feedbacks: number;
  corrections_count: number;
  avg_rating: number;
  feedback_by_type: Record<string, number>;
  recent_trend: {
    period: string;
    count: number;
    avg_rating: number;
  }[];
}

interface PreferencePair {
  prompt: string;
  chosen: string;
  rejected: string;
  rating_gap: number;
  source: string;
}

interface CorrectionExample {
  query: string;
  original_response: string;
  correction: string;
  feedback_type: string;
  timestamp: string;
}

export function FeedbackDashboard() {
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [preferencePairs, setPreferencePairs] = useState<PreferencePair[]>([]);
  const [corrections, setCorrections] = useState<CorrectionExample[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'preferences' | 'corrections' | 'export'>('overview');
  const [exportFormat, setExportFormat] = useState('raw');
  const [exportData, setExportData] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, pairsRes, correctionsRes] = await Promise.all([
        fetch('/api/feedback/stats'),
        fetch('/api/feedback/preference-pairs?limit=20'),
        fetch('/api/feedback/corrections?limit=20'),
      ]);

      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
      if (pairsRes.ok) {
        const data = await pairsRes.json();
        setPreferencePairs(data.preference_pairs || []);
      }
      if (correctionsRes.ok) {
        const data = await correctionsRes.json();
        setCorrections(data.corrections || []);
      }
    } catch (err) {
      console.error('Failed to load feedback data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const res = await fetch(`/api/feedback/export?format=${exportFormat}`);
      if (res.ok) {
        const data = await res.json();
        setExportData(data);
      }
    } catch (err) {
      console.error('Failed to export data:', err);
    }
  };

  const downloadExport = () => {
    if (!exportData) return;
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rlhf_training_data_${exportFormat}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-slate-100 mb-6">RLHF Feedback Dashboard</h1>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-slate-700">
        {(['overview', 'preferences', 'corrections', 'export'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 font-medium capitalize transition-colors ${
              activeTab === tab
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Total Feedbacks"
            value={stats.total_feedbacks}
            icon="chart"
          />
          <StatCard
            title="Positive"
            value={stats.positive_feedbacks}
            subtitle={`${((stats.positive_feedbacks / stats.total_feedbacks) * 100 || 0).toFixed(1)}%`}
            icon="thumbsUp"
            color="green"
          />
          <StatCard
            title="Negative"
            value={stats.negative_feedbacks}
            subtitle={`${((stats.negative_feedbacks / stats.total_feedbacks) * 100 || 0).toFixed(1)}%`}
            icon="thumbsDown"
            color="red"
          />
          <StatCard
            title="Corrections"
            value={stats.corrections_count}
            icon="edit"
            color="blue"
          />
        </div>
      )}

      {/* Feedback by Type */}
      {activeTab === 'overview' && stats?.feedback_by_type && (
        <div className="bg-slate-800 rounded-lg p-6 mb-8 border border-slate-700">
          <h2 className="text-lg font-semibold text-slate-100 mb-4">Feedback by Type</h2>
          <div className="space-y-3">
            {Object.entries(stats.feedback_by_type).map(([type, count]) => (
              <div key={type} className="flex items-center gap-4">
                <span className="w-24 text-slate-400 capitalize">{type}</span>
                <div className="flex-1 bg-slate-700 rounded-full h-4">
                  <div
                    className="bg-blue-500 h-4 rounded-full"
                    style={{
                      width: `${(count / stats.total_feedbacks) * 100}%`,
                    }}
                  />
                </div>
                <span className="w-12 text-right text-slate-300">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Preference Pairs Tab */}
      {activeTab === 'preferences' && (
        <div className="space-y-4">
          <p className="text-slate-400 mb-4">
            Preference pairs for Direct Preference Optimization (DPO) training.
            These are responses where users indicated a clear preference.
          </p>
          {preferencePairs.length === 0 ? (
            <div className="text-center text-slate-400 py-12">
              No preference pairs available yet. Collect more feedback to generate training data.
            </div>
          ) : (
            preferencePairs.map((pair, index) => (
              <PreferencePairCard key={index} pair={pair} />
            ))
          )}
        </div>
      )}

      {/* Corrections Tab */}
      {activeTab === 'corrections' && (
        <div className="space-y-4">
          <p className="text-slate-400 mb-4">
            User-submitted corrections for Supervised Fine-Tuning (SFT).
          </p>
          {corrections.length === 0 ? (
            <div className="text-center text-slate-400 py-12">
              No corrections submitted yet.
            </div>
          ) : (
            corrections.map((correction, index) => (
              <CorrectionCard key={index} correction={correction} />
            ))
          )}
        </div>
      )}

      {/* Export Tab */}
      {activeTab === 'export' && (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-slate-100 mb-4">Export Training Data</h2>
          <p className="text-slate-400 mb-6">
            Export feedback data in various formats for RLHF training pipelines.
          </p>

          <div className="flex gap-4 mb-6">
            <select
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded px-4 py-2 text-slate-200"
            >
              <option value="raw">Raw JSON</option>
              <option value="dpo">DPO Format</option>
              <option value="sft">SFT Format</option>
              <option value="alpaca">Alpaca Format</option>
              <option value="sharegpt">ShareGPT Format</option>
              <option value="openai">OpenAI Format</option>
            </select>
            <button
              onClick={handleExport}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              Generate Export
            </button>
          </div>

          {exportData && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-slate-300">
                  Generated {exportData.count || exportData.sft_count || 0} examples
                </span>
                <button
                  onClick={downloadExport}
                  className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                >
                  Download JSON
                </button>
              </div>
              <pre className="bg-slate-900 rounded p-4 text-sm text-slate-300 overflow-auto max-h-96">
                {JSON.stringify(exportData, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon,
  color = 'slate',
}: {
  title: string;
  value: number;
  subtitle?: string;
  icon: 'chart' | 'thumbsUp' | 'thumbsDown' | 'edit';
  color?: 'slate' | 'green' | 'red' | 'blue';
}) {
  const iconColors = {
    slate: 'text-slate-400',
    green: 'text-green-400',
    red: 'text-red-400',
    blue: 'text-blue-400',
  };

  const icons = {
    chart: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    thumbsUp: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
      </svg>
    ),
    thumbsDown: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
      </svg>
    ),
    edit: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
      </svg>
    ),
  };

  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      <div className="flex items-center justify-between mb-2">
        <span className="text-slate-400 text-sm">{title}</span>
        <span className={iconColors[color]}>{icons[icon]}</span>
      </div>
      <div className="text-2xl font-bold text-slate-100">{value}</div>
      {subtitle && <div className="text-sm text-slate-400 mt-1">{subtitle}</div>}
    </div>
  );
}

function PreferencePairCard({ pair }: { pair: PreferencePair }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-slate-400">Rating Gap: {pair.rating_gap}</span>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      </div>

      <div className="mb-3">
        <span className="text-xs text-slate-500 uppercase tracking-wide">Prompt</span>
        <p className="text-slate-200 mt-1">
          {expanded ? pair.prompt : pair.prompt.substring(0, 150) + (pair.prompt.length > 150 ? '...' : '')}
        </p>
      </div>

      {expanded && (
        <>
          <div className="mb-3 p-3 bg-green-900/20 border border-green-800 rounded">
            <span className="text-xs text-green-400 uppercase tracking-wide">Chosen Response</span>
            <p className="text-slate-200 mt-1 text-sm">{pair.chosen}</p>
          </div>

          <div className="p-3 bg-red-900/20 border border-red-800 rounded">
            <span className="text-xs text-red-400 uppercase tracking-wide">Rejected Response</span>
            <p className="text-slate-200 mt-1 text-sm">{pair.rejected}</p>
          </div>
        </>
      )}
    </div>
  );
}

function CorrectionCard({ correction }: { correction: CorrectionExample }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-slate-400 capitalize">{correction.feedback_type}</span>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      </div>

      <div className="mb-3">
        <span className="text-xs text-slate-500 uppercase tracking-wide">Query</span>
        <p className="text-slate-200 mt-1">{correction.query}</p>
      </div>

      {expanded && (
        <>
          <div className="mb-3 p-3 bg-red-900/20 border border-red-800 rounded">
            <span className="text-xs text-red-400 uppercase tracking-wide">Original Response</span>
            <p className="text-slate-200 mt-1 text-sm">{correction.original_response}</p>
          </div>

          <div className="p-3 bg-green-900/20 border border-green-800 rounded">
            <span className="text-xs text-green-400 uppercase tracking-wide">Correction</span>
            <p className="text-slate-200 mt-1 text-sm">{correction.correction}</p>
          </div>
        </>
      )}
    </div>
  );
}
