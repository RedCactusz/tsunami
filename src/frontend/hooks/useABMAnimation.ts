import { useState, useEffect, useRef, useCallback } from 'react';
import type { ABMFrame } from '@/types';

interface UseABMAnimationProps {
  frames: ABMFrame[];
  autoPlay?: boolean;
  initialSpeed?: number; // frames per second
  onFrameChange?: (frame: ABMFrame, frameIndex: number) => void;
  onAnimationComplete?: () => void;
}

interface AnimationState {
  isPlaying: boolean;
  currentFrameIndex: number;
  speed: number; // frames per second
  totalFrames: number;
  currentTime: number; // in minutes
}

export function useABMAnimation({
  frames,
  autoPlay = false,
  initialSpeed = 2, // 2 frames per second by default
  onFrameChange,
  onAnimationComplete,
}: UseABMAnimationProps) {
  const [animationState, setAnimationState] = useState<AnimationState>({
    isPlaying: autoPlay,
    currentFrameIndex: 0,
    speed: initialSpeed,
    totalFrames: frames.length,
    currentTime: frames[0]?.time_min || 0,
  });

  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Update total frames when frames change
  useEffect(() => {
    setAnimationState(prev => ({
      ...prev,
      totalFrames: frames.length,
      currentFrameIndex: Math.min(prev.currentFrameIndex, frames.length - 1),
    }));
  }, [frames.length]);

  // Get current frame
  const currentFrame = frames[animationState.currentFrameIndex] || null;

  // Animation loop
  useEffect(() => {
    if (!animationState.isPlaying || frames.length === 0) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    const intervalMs = 1000 / animationState.speed;

    intervalRef.current = setInterval(() => {
      setAnimationState(prev => {
        const nextIndex = prev.currentFrameIndex + 1;

        if (nextIndex >= frames.length) {
          // Animation complete
          if (onAnimationComplete) {
            onAnimationComplete();
          }
          return {
            ...prev,
            isPlaying: false,
            currentFrameIndex: frames.length - 1,
          };
        }

        const nextFrame = frames[nextIndex];
        if (onFrameChange && nextFrame) {
          onFrameChange(nextFrame, nextIndex);
        }

        return {
          ...prev,
          currentFrameIndex: nextIndex,
          currentTime: nextFrame?.time_min || prev.currentTime,
        };
      });
    }, intervalMs);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [animationState.isPlaying, animationState.speed, frames, onFrameChange, onAnimationComplete]);

  // Control functions
  const play = useCallback(() => {
    setAnimationState(prev => ({ ...prev, isPlaying: true }));
  }, []);

  const pause = useCallback(() => {
    setAnimationState(prev => ({ ...prev, isPlaying: false }));
  }, []);

  const stop = useCallback(() => {
    setAnimationState(prev => ({
      ...prev,
      isPlaying: false,
      currentFrameIndex: 0,
      currentTime: frames[0]?.time_min || 0,
    }));
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
  }, [frames]);

  const nextFrame = useCallback(() => {
    setAnimationState(prev => {
      const nextIndex = Math.min(prev.currentFrameIndex + 1, prev.totalFrames - 1);
      const nextFrame = frames[nextIndex];
      if (onFrameChange && nextFrame) {
        onFrameChange(nextFrame, nextIndex);
      }
      return {
        ...prev,
        currentFrameIndex: nextIndex,
        currentTime: nextFrame?.time_min || prev.currentTime,
        isPlaying: false,
      };
    });
  }, [frames, onFrameChange]);

  const previousFrame = useCallback(() => {
    setAnimationState(prev => {
      const prevIndex = Math.max(prev.currentFrameIndex - 1, 0);
      const prevFrame = frames[prevIndex];
      if (onFrameChange && prevFrame) {
        onFrameChange(prevFrame, prevIndex);
      }
      return {
        ...prev,
        currentFrameIndex: prevIndex,
        currentTime: prevFrame?.time_min || prev.currentTime,
        isPlaying: false,
      };
    });
  }, [frames, onFrameChange]);

  const seekToFrame = useCallback((frameIndex: number) => {
    const clampedIndex = Math.max(0, Math.min(frameIndex, frames.length - 1));
    setAnimationState(prev => {
      const frame = frames[clampedIndex];
      if (onFrameChange && frame) {
        onFrameChange(frame, clampedIndex);
      }
      return {
        ...prev,
        currentFrameIndex: clampedIndex,
        currentTime: frame?.time_min || prev.currentTime,
      };
    });
  }, [frames, onFrameChange]);

  const setSpeed = useCallback((speed: number) => {
    setAnimationState(prev => ({ ...prev, speed }));
  }, []);

  // Calculate progress percentage
  const progress = animationState.totalFrames > 0
    ? (animationState.currentFrameIndex / (animationState.totalFrames - 1)) * 100
    : 0;

  // Calculate remaining frames
  const remainingFrames = animationState.totalFrames - animationState.currentFrameIndex - 1;

  // Calculate estimated time remaining (in seconds)
  const estimatedTimeRemaining = animationState.isPlaying && animationState.speed > 0
    ? remainingFrames / animationState.speed
    : 0;

  return {
    // State
    currentFrame,
    currentFrameIndex: animationState.currentFrameIndex,
    isPlaying: animationState.isPlaying,
    speed: animationState.speed,
    totalFrames: animationState.totalFrames,
    currentTime: animationState.currentTime,
    progress,
    remainingFrames,
    estimatedTimeRemaining,

    // Controls
    play,
    pause,
    stop,
    nextFrame,
    previousFrame,
    seekToFrame,
    setSpeed,

    // Utilities
    canPlay: frames.length > 0 && animationState.currentFrameIndex < frames.length - 1,
    canPause: animationState.isPlaying,
    canNext: animationState.currentFrameIndex < frames.length - 1,
    canPrevious: animationState.currentFrameIndex > 0,
  };
}
