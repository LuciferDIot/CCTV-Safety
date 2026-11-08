'use client'

import React from 'react'
import { Play, Pause } from 'lucide-react'

interface VideoScrubberProps {
  isPlaying: boolean
  currentTime: number
  duration: number
  videoViewMode: 'raw' | 'analyzed'
  onTogglePlay: () => void
  onSeek: (e: React.ChangeEvent<HTMLInputElement>) => void
}

export function formatSecs(sec: number) {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  const ms = Math.floor((sec % 1) * 10)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${ms}`
}

export const VideoScrubber: React.FC<VideoScrubberProps> = ({
  isPlaying,
  currentTime,
  duration,
  videoViewMode,
  onTogglePlay,
  onSeek,
}) => {
  return (
    <div className="video-scrubber-bar">
      <button
        onClick={onTogglePlay}
        className="icon-button"
        style={{ color: '#4ade80', background: 'rgba(16,37,26,0.85)', padding: 7, borderRadius: '50%' }}
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? <Pause size={16} /> : <Play size={16} />}
      </button>

      <div className="time-display">
        <span>{formatSecs(currentTime)}</span> / <span>{formatSecs(duration)}</span>
      </div>

      <input
        type="range"
        min="0"
        max={duration || 100}
        step="0.05"
        value={currentTime}
        onChange={onSeek}
        className="scrubber-slider"
        aria-label="Video scrubber"
      />

      <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#6ee7b7' }}>
        {videoViewMode === 'analyzed' ? 'AI ANNOTATED STREAM' : 'RAW CCTV STREAM'}
      </span>
    </div>
  )
}

