/**
 * MedicalAlertInline Component
 *
 * Displays medical safety alerts inline within chat messages.
 * Color-coded by severity: CRITICAL (red), HIGH (orange), MODERATE (yellow), LOW (blue), INFO (gray)
 */

import React, { useState } from 'react';
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp, Pill, Heart, Syringe } from 'lucide-react';
import type { MedicalAlert } from '../../types/chat';

interface MedicalAlertInlineProps {
  alerts: MedicalAlert[];
}

const severityConfig = {
  CRITICAL: {
    bg: 'bg-red-900/60',
    border: 'border-red-500',
    text: 'text-red-200',
    icon: AlertTriangle,
    iconColor: 'text-red-400',
    label: 'Critical',
  },
  HIGH: {
    bg: 'bg-orange-900/50',
    border: 'border-orange-500',
    text: 'text-orange-200',
    icon: AlertTriangle,
    iconColor: 'text-orange-400',
    label: 'High Priority',
  },
  MODERATE: {
    bg: 'bg-yellow-900/40',
    border: 'border-yellow-600',
    text: 'text-yellow-200',
    icon: AlertCircle,
    iconColor: 'text-yellow-400',
    label: 'Moderate',
  },
  LOW: {
    bg: 'bg-blue-900/40',
    border: 'border-blue-500',
    text: 'text-blue-200',
    icon: Info,
    iconColor: 'text-blue-400',
    label: 'Low',
  },
  INFO: {
    bg: 'bg-slate-800/60',
    border: 'border-slate-600',
    text: 'text-slate-300',
    icon: Info,
    iconColor: 'text-slate-400',
    label: 'Info',
  },
};

const categoryConfig = {
  drug_interaction: {
    icon: Pill,
    label: 'Drug Interaction',
  },
  contraindication: {
    icon: AlertCircle,
    label: 'Contraindication',
  },
  allergy: {
    icon: Syringe,
    label: 'Allergy Alert',
  },
  symptom_pattern: {
    icon: Heart,
    label: 'Symptom Pattern',
  },
};

function SingleAlert({ alert }: { alert: MedicalAlert }) {
  const [expanded, setExpanded] = useState(false);
  const severity = severityConfig[alert.severity];
  const category = categoryConfig[alert.category];
  const SeverityIcon = severity.icon;
  const CategoryIcon = category?.icon || AlertCircle;

  return (
    <div
      className={`
        rounded-lg border-l-4 ${severity.bg} ${severity.border}
        overflow-hidden transition-all duration-200
      `}
    >
      <div
        className="flex items-start gap-2 px-3 py-2 cursor-pointer hover:bg-white/5"
        onClick={() => setExpanded(!expanded)}
      >
        <SeverityIcon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${severity.iconColor}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold ${severity.text}`}>
              {severity.label}
            </span>
            <span className="text-xs text-slate-500">•</span>
            <span className="text-xs text-slate-400 flex items-center gap-1">
              <CategoryIcon className="w-3 h-3" />
              {category?.label || alert.category}
            </span>
          </div>
          <p className={`text-sm mt-1 ${severity.text}`}>
            {alert.message}
          </p>
        </div>
        <button className="p-1 hover:bg-white/10 rounded">
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </button>
      </div>

      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-white/10">
          {alert.recommendation && (
            <div className="mb-2">
              <span className="text-xs text-slate-400 font-medium">Recommendation:</span>
              <p className="text-xs text-slate-300 mt-1">{alert.recommendation}</p>
            </div>
          )}
          {alert.triggered_by && alert.triggered_by.length > 0 && (
            <div className="mb-2">
              <span className="text-xs text-slate-400 font-medium">Triggered by:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {alert.triggered_by.map((item, i) => (
                  <span
                    key={i}
                    className="text-xs bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}
          {alert.rule_id && (
            <div className="text-xs text-slate-500 mt-1">
              Rule: {alert.rule_id}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function MedicalAlertInline({ alerts }: MedicalAlertInlineProps) {
  if (!alerts || alerts.length === 0) return null;

  // Sort by severity: CRITICAL first, then HIGH, etc.
  const severityOrder = ['CRITICAL', 'HIGH', 'MODERATE', 'LOW', 'INFO'];
  const sortedAlerts = [...alerts].sort(
    (a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity)
  );

  // Check if we have critical or high severity alerts
  const hasCritical = alerts.some(a => a.severity === 'CRITICAL');
  const hasHigh = alerts.some(a => a.severity === 'HIGH');

  return (
    <div className="space-y-2 mb-3">
      {/* Header if multiple alerts */}
      {alerts.length > 1 && (
        <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
          <AlertTriangle className={`w-3 h-3 ${hasCritical ? 'text-red-400' : hasHigh ? 'text-orange-400' : 'text-yellow-400'}`} />
          <span>
            {alerts.length} medical alert{alerts.length > 1 ? 's' : ''} detected
          </span>
        </div>
      )}

      {/* Individual alerts */}
      {sortedAlerts.map((alert, index) => (
        <SingleAlert key={`${alert.rule_id || index}-${index}`} alert={alert} />
      ))}
    </div>
  );
}
