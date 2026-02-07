import React from 'react';
import { Star } from 'lucide-react';

interface RatingVisualizationProps {
  rating: number; // 0-5 or 0-1 scale
  maxRating?: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  showValue?: boolean;
}

export function RatingVisualization({
  rating,
  maxRating = 5,
  size = 'md',
  showLabel = false,
  showValue = true,
}: RatingVisualizationProps) {
  // Normalize to 0-5 scale if needed
  const normalizedRating = maxRating === 1 ? rating * 5 : rating;
  const percentage = (normalizedRating / 5) * 100;

  const sizeClasses = {
    sm: { star: 'w-3 h-3', text: 'text-xs', gap: 'gap-0.5' },
    md: { star: 'w-4 h-4', text: 'text-sm', gap: 'gap-1' },
    lg: { star: 'w-5 h-5', text: 'text-base', gap: 'gap-1.5' },
  };

  const ratingColor =
    normalizedRating >= 4 ? 'text-green-400' :
    normalizedRating >= 3 ? 'text-blue-400' :
    normalizedRating >= 2 ? 'text-yellow-400' :
    'text-red-400';

  const ratingLabel =
    normalizedRating >= 4.5 ? 'Excellent' :
    normalizedRating >= 3.5 ? 'Good' :
    normalizedRating >= 2.5 ? 'Average' :
    normalizedRating >= 1.5 ? 'Poor' :
    'Very Poor';

  return (
    <div className="flex items-center gap-2">
      {/* Stars */}
      <div className={`flex ${sizeClasses[size].gap}`}>
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`${sizeClasses[size].star} ${
              star <= Math.round(normalizedRating)
                ? 'fill-yellow-400 text-yellow-400'
                : 'fill-slate-700 text-slate-700'
            }`}
          />
        ))}
      </div>

      {/* Value */}
      {showValue && (
        <span className={`${sizeClasses[size].text} ${ratingColor} font-medium`}>
          {normalizedRating.toFixed(1)}
        </span>
      )}

      {/* Label */}
      {showLabel && (
        <span className={`${sizeClasses[size].text} text-slate-400`}>
          ({ratingLabel})
        </span>
      )}
    </div>
  );
}

// Gauge-style rating visualization
interface RatingGaugeProps {
  rating: number; // 0-1 scale
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function RatingGauge({ rating, label, size = 'md' }: RatingGaugeProps) {
  const percentage = Math.round(rating * 100);

  const colorClass =
    percentage >= 80 ? 'text-green-400' :
    percentage >= 60 ? 'text-blue-400' :
    percentage >= 40 ? 'text-yellow-400' :
    'text-red-400';

  const bgColorClass =
    percentage >= 80 ? 'bg-green-500' :
    percentage >= 60 ? 'bg-blue-500' :
    percentage >= 40 ? 'bg-yellow-500' :
    'bg-red-500';

  const sizeClasses = {
    sm: { container: 'w-12 h-12', text: 'text-sm', label: 'text-xs' },
    md: { container: 'w-16 h-16', text: 'text-lg', label: 'text-xs' },
    lg: { container: 'w-20 h-20', text: 'text-xl', label: 'text-sm' },
  };

  return (
    <div className="flex flex-col items-center gap-1">
      <div className={`relative ${sizeClasses[size].container}`}>
        {/* Background circle */}
        <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
          <path
            d="M18 2.0845
              a 15.9155 15.9155 0 0 1 0 31.831
              a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none"
            stroke="#334155"
            strokeWidth="3"
          />
          <path
            d="M18 2.0845
              a 15.9155 15.9155 0 0 1 0 31.831
              a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeDasharray={`${percentage}, 100`}
            className={colorClass}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`${sizeClasses[size].text} font-bold ${colorClass}`}>
            {percentage}%
          </span>
        </div>
      </div>
      {label && (
        <span className={`${sizeClasses[size].label} text-slate-400`}>{label}</span>
      )}
    </div>
  );
}

// Horizontal bar rating
interface RatingBarProps {
  rating: number; // 0-1 scale
  label?: string;
  showPercentage?: boolean;
}

export function RatingBar({ rating, label, showPercentage = true }: RatingBarProps) {
  const percentage = Math.round(rating * 100);

  const colorClass =
    percentage >= 80 ? 'bg-green-500' :
    percentage >= 60 ? 'bg-blue-500' :
    percentage >= 40 ? 'bg-yellow-500' :
    'bg-red-500';

  return (
    <div className="space-y-1">
      {(label || showPercentage) && (
        <div className="flex justify-between text-xs">
          {label && <span className="text-slate-400">{label}</span>}
          {showPercentage && <span className="text-slate-300 font-medium">{percentage}%</span>}
        </div>
      )}
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClass} rounded-full transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
