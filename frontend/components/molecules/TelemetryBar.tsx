'use client'

import React from 'react'
import { StatusDot } from '@/components/atoms'
import type { TelemetryHUD, SystemHealth } from '@/lib/api'

interface TelemetryBarProps {
  telemetry: TelemetryHUD
  health: SystemHealth | null
  selectedVideo: string
}

export const TelemetryBar: React.FC<TelemetryBarProps> = ({ telemetry, health, selectedVideo }) => {
  return (
    <div className="telemetry-bar">
      <div className="telemetry-context">
        <StatusDot /> SYSTEM ACTIVE
        <span className="telemetry-divider" />
        <span>
          Device: <strong style={{ color: '#93c5fd' }}>{health?.device?.toUpperCase() || 'CPU'}</strong>
        </span>
        <span className="telemetry-divider" />
        <span className="telemetry-muted">Video: {selectedVideo || 'No video loaded'}</span>
      </div>

      <div className="hud">
        <div className="hud-metric">
          <span>FPS</span>
          <strong style={{ color: '#4ade80' }}>{telemetry.fps.toFixed(1)}</strong>
        </div>
        <div className="hud-metric">
          <span>Active Tracks</span>
          <strong style={{ color: '#60a5fa' }}>{telemetry.active_tracks}</strong>
        </div>
        <div className="hud-metric">
          <span>Stitched IDs</span>
          <strong style={{ color: '#f472b6' }}>{telemetry.stitched_ids}</strong>
        </div>
        <div className="hud-metric">
          <span>Latency</span>
          <strong style={{ color: '#fbbf24' }}>{telemetry.latency_ms.toFixed(0)}ms</strong>
        </div>
        <div className="hud-metric">
          <span>Server Uptime</span>
          <strong>{health ? `${Math.round(health.uptime_seconds)}s` : 'Active'}</strong>
        </div>
      </div>
    </div>
  )
}

