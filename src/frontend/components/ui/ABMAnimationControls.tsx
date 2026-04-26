'use client';

import { Play, Pause, SkipBack, SkipForward, RotateCcw } from 'lucide-react';

interface ABMAnimationControlsProps {
  isPlaying: boolean;
  currentFrame: number;
  totalFrames: number;
  currentTime: number; // in minutes
  progress: number;
  speed: number;
  canPlay: boolean;
  canPause: boolean;
  canNext: boolean;
  canPrevious: boolean;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onNext: () => void;
  onPrevious: () => void;
  onSeek: (frameIndex: number) => void;
  onSpeedChange: (speed: number) => void;
}

export default function ABMAnimationControls({
  isPlaying,
  currentFrame,
  totalFrames,
  currentTime,
  progress,
  speed,
  canPlay,
  canPause,
  canNext,
  canPrevious,
  onPlay,
  onPause,
  onStop,
  onNext,
  onPrevious,
  onSeek,
  onSpeedChange,
}: ABMAnimationControlsProps) {
  const speedOptions = [0.5, 1, 2, 4, 8];

  const formatTime = (minutes: number): string => {
    const mins = Math.floor(minutes);
    const secs = Math.round((minutes - mins) * 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-white/95 backdrop-blur-sm rounded-lg shadow-lg border border-gray-200 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">Animasi Evakuasi</h3>
        <div className="text-xs text-gray-500">
          Frame {currentFrame + 1} / {totalFrames}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-200 ease-out"
            style={{ width: `${progress}%` }}
          />
          {/* Draggable thumb */}
          <input
            type="range"
            min="0"
            max={totalFrames - 1}
            value={currentFrame}
            onChange={(e) => onSeek(parseInt(e.target.value))}
            className="absolute top-0 left-0 w-full h-full opacity-0 cursor-pointer"
            disabled={isPlaying}
          />
        </div>

        {/* Time labels */}
        <div className="flex justify-between text-xs text-gray-500">
          <span>{formatTime(currentTime)}</span>
          <span>Frame {currentFrame + 1}</span>
        </div>
      </div>

      {/* Control Buttons */}
      <div className="flex items-center justify-center gap-2">
        {/* Stop/Reset */}
        <button
          onClick={onStop}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-600 transition-colors"
          title="Reset ke awal"
        >
          <RotateCcw size={20} />
        </button>

        {/* Previous Frame */}
        <button
          onClick={onPrevious}
          disabled={!canPrevious || isPlaying}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          title="Frame sebelumnya"
        >
          <SkipBack size={20} />
        </button>

        {/* Play/Pause */}
        <button
          onClick={isPlaying ? onPause : onPlay}
          disabled={!canPlay && !canPause}
          className="p-3 rounded-lg bg-blue-500 hover:bg-blue-600 text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed shadow-md"
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause size={24} /> : <Play size={24} />}
        </button>

        {/* Next Frame */}
        <button
          onClick={onNext}
          disabled={!canNext || isPlaying}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          title="Frame berikutnya"
        >
          <SkipForward size={20} />
        </button>
      </div>

      {/* Speed Control */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 font-medium">Kecepatan:</span>
        <div className="flex gap-1">
          {speedOptions.map((option) => (
            <button
              key={option}
              onClick={() => onSpeedChange(option)}
              className={`px-2 py-1 text-xs rounded-md transition-all ${
                speed === option
                  ? 'bg-blue-500 text-white font-medium'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {option}x
            </button>
          ))}
        </div>
      </div>

      {/* Status Indicator */}
      {isPlaying && (
        <div className="flex items-center gap-2 text-xs text-blue-600">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
          <span>Memutar animasi...</span>
        </div>
      )}
    </div>
  );
}
