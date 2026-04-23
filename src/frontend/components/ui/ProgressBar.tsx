'use client';

import React, { useEffect, useState } from 'react';

interface ProgressBarProps {
  progress: number; // 0-100
  label?: string;
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple';
  size?: 'sm' | 'md' | 'lg';
  showPercentage?: boolean;
  animated?: boolean;
  className?: string;
}

export default function ProgressBar({
  progress,
  label = '',
  color = 'blue',
  size = 'md',
  showPercentage = true,
  animated = true,
  className = ''
}: ProgressBarProps) {
  const [displayProgress, setDisplayProgress] = useState(0);

  useEffect(() => {
    if (animated) {
      const timer = setTimeout(() => {
        setDisplayProgress(progress);
      }, 100);
      return () => clearTimeout(timer);
    } else {
      setDisplayProgress(progress);
    }
  }, [progress, animated]);

  const colorClasses = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
    purple: 'bg-purple-500'
  };

  const sizeClasses = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3'
  };

  return (
    <div className={`space-y-2 ${className}`}>
      {(label || showPercentage) && (
        <div className="flex justify-between items-center">
          {label && <span className="text-sm font-medium text-gray-700">{label}</span>}
          {showPercentage && (
            <span className="text-sm font-bold text-gray-800">{Math.round(displayProgress)}%</span>
          )}
        </div>
      )}

      <div className={`w-full bg-gray-200 rounded-full overflow-hidden ${sizeClasses[size]}`}>
        <div
          className={`h-full ${colorClasses[color]} transition-all duration-500 ease-out rounded-full ${
            animated ? 'transition-all duration-500 ease-out' : ''
          }`}
          style={{ width: `${displayProgress}%` }}
        />
      </div>
    </div>
  );
}

// Specialized progress bar for simulation steps
interface SimulationProgressProps {
  currentStep: number;
  totalSteps: number;
  stepLabels: string[];
  isRunning: boolean;
  className?: string;
}

export function SimulationProgress({
  currentStep,
  totalSteps,
  stepLabels,
  isRunning,
  className = ''
}: SimulationProgressProps) {
  const progress = (currentStep / totalSteps) * 100;

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex justify-between items-center">
        <span className="text-sm font-semibold text-gray-800">
          {isRunning ? 'Menjalankan Simulasi...' : 'Simulasi Selesai'}
        </span>
        <span className="text-sm text-gray-600">
          {currentStep}/{totalSteps}
        </span>
      </div>

      <ProgressBar
        progress={progress}
        color={isRunning ? 'blue' : 'green'}
        size="lg"
        animated={true}
      />

      <div className="space-y-2">
        {stepLabels.map((label, index) => (
          <div
            key={index}
            className={`flex items-center gap-3 p-2 rounded-md transition-colors ${
              index < currentStep
                ? 'bg-green-50 border border-green-200'
                : index === currentStep && isRunning
                ? 'bg-blue-50 border border-blue-200 animate-pulse'
                : 'bg-gray-50 border border-gray-200'
            }`}
          >
            <div className={`w-4 h-4 rounded-full flex items-center justify-center text-xs ${
              index < currentStep
                ? 'bg-green-500 text-white'
                : index === currentStep && isRunning
                ? 'bg-blue-500 text-white animate-spin'
                : 'bg-gray-300 text-gray-600'
            }`}>
              {index < currentStep ? '✓' : index === currentStep && isRunning ? '⟳' : index + 1}
            </div>
            <span className={`text-sm ${
              index < currentStep
                ? 'text-green-700 font-medium'
                : index === currentStep && isRunning
                ? 'text-blue-700 font-medium'
                : 'text-gray-600'
            }`}>
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Real-time progress with ETA
interface RealTimeProgressProps {
  progress: number;
  label: string;
  startTime?: number;
  estimatedTotalTime?: number;
  className?: string;
}

export function RealTimeProgress({
  progress,
  label,
  startTime,
  estimatedTotalTime,
  className = ''
}: RealTimeProgressProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) return;

    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime]);

  const formatTime = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  };

  const eta = estimatedTotalTime && progress > 0
    ? ((100 - progress) / progress) * elapsed
    : 0;

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <div className="text-right">
          <div className="text-sm font-bold text-gray-800">{Math.round(progress)}%</div>
          {startTime && (
            <div className="text-xs text-gray-600">
              {formatTime(elapsed)}
              {eta > 0 && ` • ETA: ${formatTime(eta)}`}
            </div>
          )}
        </div>
      </div>

      <ProgressBar
        progress={progress}
        color="blue"
        size="md"
        animated={true}
      />
    </div>
  );
}