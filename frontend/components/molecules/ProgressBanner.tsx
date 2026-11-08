'use client'

import React from 'react'
import { Loader2, CheckCircle2, AlertCircle, X } from 'lucide-react'
import type { PipelineStatusResponse } from '@/lib/api'

interface ProgressBannerProps {
  activeTask: PipelineStatusResponse
  onCancel: () => void
  onDismiss: () => void
}

export const ProgressBanner: React.FC<ProgressBannerProps> = ({ activeTask, onCancel, onDismiss }) => {
  return (
    <div className="progress-banner">
      <div className="progress-top">
        <div className="progress-title">
          {activeTask.status === 'running' && <Loader2 size={15} className="animate-spin" />}
          {activeTask.status === 'completed' && <CheckCircle2 size={15} style={{ color: '#4ade80' }} />}
          {activeTask.status === 'failed' && <AlertCircle size={15} style={{ color: '#fb7185' }} />}
          {activeTask.status === 'cancelled' && <AlertCircle size={15} style={{ color: '#fbbf24' }} />}
          <span>
            {activeTask.status === 'running' && `AI RENDERING IN PROGRESS · ${activeTask.progress_pct.toFixed(0)}%`}
            {activeTask.status === 'completed' && `ANALYSIS & ANNOTATED VIDEO READY (100%)`}
            {activeTask.status === 'cancelled' && `ANALYSIS JOB CANCELLED`}
            {activeTask.status === 'failed' && `ANALYSIS FAILED: ${activeTask.error || 'Execution error'}`}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {activeTask.status === 'running' && (
            <button className="progress-cancel-btn" onClick={onCancel}>
              <X size={12} /> Cancel Render
            </button>
          )}
          {activeTask.status !== 'running' && (
            <button className="icon-button" onClick={onDismiss} title="Dismiss banner">
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${Math.min(100, activeTask.progress_pct)}%` }} />
      </div>

      <div className="progress-metrics">
        <span>Frame: <strong style={{ color: '#f1f5f9' }}>{activeTask.current_frame}</strong> / {activeTask.total_frames}</span>
        <span>Speed: <strong style={{ color: '#4ade80' }}>{activeTask.fps.toFixed(1)} FPS</strong></span>
        <span>Elapsed: <strong style={{ color: '#93c5fd' }}>{activeTask.elapsed_seconds.toFixed(1)}s</strong></span>
        {activeTask.eta_seconds != null && activeTask.status === 'running' && (
          <span>ETA: <strong style={{ color: '#fbbf24' }}>{activeTask.eta_seconds.toFixed(0)}s left</strong></span>
        )}
        <span>Violations Found: <strong style={{ color: '#fb7185' }}>{activeTask.events_detected}</strong></span>
      </div>
    </div>
  )
}

