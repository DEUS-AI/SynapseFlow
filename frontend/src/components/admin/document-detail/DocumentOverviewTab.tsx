import React from 'react';
import {
  FileText,
  Calendar,
  Clock,
  Tag,
  Database,
  Link2,
  BarChart3,
} from 'lucide-react';
import { formatDateTime } from '../../../utils/formatTime';

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
  file_size?: number;
  page_count?: number;
}

interface DocumentOverviewTabProps {
  document: DocumentData;
}

export function DocumentOverviewTab({ document }: DocumentOverviewTabProps) {
  const qualityColor =
    document.quality_level === 'excellent' ? 'text-green-400' :
    document.quality_level === 'good' ? 'text-blue-400' :
    document.quality_level === 'acceptable' ? 'text-yellow-400' :
    document.quality_level === 'poor' ? 'text-orange-400' :
    'text-red-400';

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Database className="w-5 h-5" />}
          label="Entities"
          value={document.entity_count ?? 0}
          color="text-blue-400"
        />
        <StatCard
          icon={<Link2 className="w-5 h-5" />}
          label="Relationships"
          value={document.relationship_count ?? 0}
          color="text-purple-400"
        />
        <StatCard
          icon={<BarChart3 className="w-5 h-5" />}
          label="Quality Score"
          value={document.quality_score !== undefined ? `${(document.quality_score * 100).toFixed(0)}%` : 'N/A'}
          color={qualityColor}
        />
        <StatCard
          icon={<Tag className="w-5 h-5" />}
          label="Category"
          value={document.category || 'Uncategorized'}
          color="text-slate-400"
        />
      </div>

      {/* Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Info */}
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
          <h3 className="text-lg font-medium text-slate-200 mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-400" />
            Document Information
          </h3>
          <dl className="space-y-3">
            <DetailRow label="Filename" value={document.filename} />
            <DetailRow label="Document ID" value={document.id} mono />
            <DetailRow label="Status" value={
              <span className={`px-2 py-0.5 rounded-full text-xs ${
                document.status === 'completed' ? 'bg-green-900/50 text-green-400' :
                document.status === 'processing' ? 'bg-blue-900/50 text-blue-400' :
                document.status === 'failed' ? 'bg-red-900/50 text-red-400' :
                'bg-slate-700 text-slate-400'
              }`}>
                {document.status}
              </span>
            } />
            {document.file_size && (
              <DetailRow label="File Size" value={formatFileSize(document.file_size)} />
            )}
            {document.page_count && (
              <DetailRow label="Pages" value={document.page_count.toString()} />
            )}
          </dl>
        </div>

        {/* Processing Info */}
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
          <h3 className="text-lg font-medium text-slate-200 mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-green-400" />
            Processing Timeline
          </h3>
          <dl className="space-y-3">
            <DetailRow
              label="Uploaded"
              value={document.created_at ? formatDateTime(document.created_at) : 'Unknown'}
              icon={<Calendar className="w-4 h-4 text-slate-500" />}
            />
            <DetailRow
              label="Processed"
              value={document.processed_at ? formatDateTime(document.processed_at) : 'Not processed'}
              icon={<Clock className="w-4 h-4 text-slate-500" />}
            />
            {document.markdown_path && (
              <DetailRow
                label="Markdown Output"
                value={document.markdown_path.split('/').pop() || document.markdown_path}
                mono
              />
            )}
          </dl>
        </div>

        {/* Quality Summary */}
        {document.quality_score !== undefined && (
          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700 lg:col-span-2">
            <h3 className="text-lg font-medium text-slate-200 mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-yellow-400" />
              Quality Assessment
            </h3>
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className={`text-4xl font-bold ${qualityColor}`}>
                  {(document.quality_score * 100).toFixed(0)}%
                </div>
                <div className={`text-sm ${qualityColor} mt-1 capitalize`}>
                  {document.quality_level || 'Unknown'}
                </div>
              </div>
              <div className="flex-1">
                <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      document.quality_level === 'excellent' ? 'bg-green-500' :
                      document.quality_level === 'good' ? 'bg-blue-500' :
                      document.quality_level === 'acceptable' ? 'bg-yellow-500' :
                      document.quality_level === 'poor' ? 'bg-orange-500' :
                      'bg-red-500'
                    }`}
                    style={{ width: `${document.quality_score * 100}%` }}
                  />
                </div>
                <p className="text-sm text-slate-400 mt-2">
                  View the Quality tab for detailed metrics and recommendations.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Helper components
function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg bg-slate-800 ${color}`}>{icon}</div>
        <div>
          <p className="text-xs text-slate-400">{label}</p>
          <p className={`text-lg font-semibold ${color}`}>{value}</p>
        </div>
      </div>
    </div>
  );
}

function DetailRow({
  label,
  value,
  icon,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between items-start gap-4">
      <dt className="text-sm text-slate-400 flex items-center gap-2">
        {icon}
        {label}
      </dt>
      <dd className={`text-sm text-slate-200 text-right ${mono ? 'font-mono text-xs' : ''}`}>
        {value}
      </dd>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
