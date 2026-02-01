import React from 'react';

interface CorrectionDiffViewProps {
  original: string;
  corrected: string;
  className?: string;
}

// Simple word-level diff
function computeDiff(original: string, corrected: string): { type: 'same' | 'removed' | 'added'; text: string }[] {
  const originalWords = original.split(/(\s+)/);
  const correctedWords = corrected.split(/(\s+)/);
  const result: { type: 'same' | 'removed' | 'added'; text: string }[] = [];

  // Simple LCS-based diff (simplified for performance)
  const originalSet = new Set(originalWords);
  const correctedSet = new Set(correctedWords);

  let i = 0;
  let j = 0;

  while (i < originalWords.length || j < correctedWords.length) {
    if (i < originalWords.length && j < correctedWords.length && originalWords[i] === correctedWords[j]) {
      // Same word
      result.push({ type: 'same', text: originalWords[i] });
      i++;
      j++;
    } else if (i < originalWords.length && !correctedSet.has(originalWords[i])) {
      // Word removed
      result.push({ type: 'removed', text: originalWords[i] });
      i++;
    } else if (j < correctedWords.length && !originalSet.has(correctedWords[j])) {
      // Word added
      result.push({ type: 'added', text: correctedWords[j] });
      j++;
    } else if (i < originalWords.length) {
      // Word removed
      result.push({ type: 'removed', text: originalWords[i] });
      i++;
    } else if (j < correctedWords.length) {
      // Word added
      result.push({ type: 'added', text: correctedWords[j] });
      j++;
    }
  }

  return result;
}

export function CorrectionDiffView({ original, corrected, className = '' }: CorrectionDiffViewProps) {
  const diff = computeDiff(original, corrected);

  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 gap-4 ${className}`}>
      {/* Original */}
      <div>
        <label className="text-xs font-medium text-red-400 uppercase tracking-wide flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-red-500" />
          Original
        </label>
        <div className="mt-2 p-3 bg-red-900/10 border border-red-800/30 rounded-lg text-sm">
          <p className="text-slate-200 whitespace-pre-wrap leading-relaxed">
            {original}
          </p>
        </div>
      </div>

      {/* Corrected */}
      <div>
        <label className="text-xs font-medium text-green-400 uppercase tracking-wide flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-green-500" />
          Corrected
        </label>
        <div className="mt-2 p-3 bg-green-900/10 border border-green-800/30 rounded-lg text-sm">
          <p className="text-slate-200 whitespace-pre-wrap leading-relaxed">
            {corrected}
          </p>
        </div>
      </div>

      {/* Inline diff view */}
      <div className="md:col-span-2">
        <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
          Changes
        </label>
        <div className="mt-2 p-3 bg-slate-900/50 border border-slate-700 rounded-lg text-sm">
          <p className="leading-relaxed">
            {diff.map((part, i) => (
              <span
                key={i}
                className={
                  part.type === 'removed'
                    ? 'bg-red-900/50 text-red-300 line-through px-0.5 rounded'
                    : part.type === 'added'
                    ? 'bg-green-900/50 text-green-300 px-0.5 rounded'
                    : 'text-slate-300'
                }
              >
                {part.text}
              </span>
            ))}
          </p>
        </div>
      </div>
    </div>
  );
}

// Compact inline diff for smaller displays
export function InlineDiff({ original, corrected }: { original: string; corrected: string }) {
  const diff = computeDiff(original, corrected);

  return (
    <span>
      {diff.map((part, i) => (
        <span
          key={i}
          className={
            part.type === 'removed'
              ? 'bg-red-900/50 text-red-300 line-through'
              : part.type === 'added'
              ? 'bg-green-900/50 text-green-300'
              : ''
          }
        >
          {part.text}
        </span>
      ))}
    </span>
  );
}
