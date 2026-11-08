'use client'

import React from 'react'
import {
  ScanLine,
  Maximize2,
  RotateCcw,
  Save,
  Upload,
  Video,
  Loader2,
} from 'lucide-react'
import { VideoScrubber } from '@/components/molecules'
import { Button } from '@/components/atoms'
import { getVideoStreamUrl, type IntersectionZonesConfig } from '@/lib/api'

interface VideoPlayerCanvasProps {
  selectedVideo: string
  currentStreamFile: string
  baseVideoStem: string
  annotatedVideoExists: boolean
  videoViewMode: 'raw' | 'analyzed'
  mode: 'view' | 'edit'
  activeZoneTab: 'road' | 'crosswalk'
  crosswalkEnabled: boolean
  zones: IntersectionZonesConfig | null
  draggingVertex: { zone: 'crosswalk' | 'road'; index: number } | null
  isDraggingOver: boolean
  isUploading: boolean
  isPlaying: boolean
  currentTime: number
  duration: number
  videoRef: React.RefObject<HTMLVideoElement | null>
  onSetVideoViewMode: (vm: 'raw' | 'analyzed') => void
  onSetActiveZoneTab: (zt: 'road' | 'crosswalk') => void
  onToggleCrosswalk: (enabled: boolean) => void
  onResetZones: () => void
  onSaveZones?: () => void
  onTogglePlay: () => void
  onTimeUpdate: () => void
  onSeek: (e: React.ChangeEvent<HTMLInputElement>) => void
  onSvgPointerMove: (e: React.PointerEvent<SVGSVGElement>) => void
  onSvgPointerUp: () => void
  onDragVertexStart: (zone: 'crosswalk' | 'road', index: number) => void
  onDragOver: (e: React.DragEvent) => void
  onDragLeave: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent) => void
  onUploadClick: () => void
  onLoadSample: () => void
}

export const VideoPlayerCanvas: React.FC<VideoPlayerCanvasProps> = ({
  selectedVideo,
  currentStreamFile,
  baseVideoStem,
  annotatedVideoExists,
  videoViewMode,
  mode,
  activeZoneTab,
  crosswalkEnabled,
  zones,
  draggingVertex,
  isDraggingOver,
  isUploading,
  isPlaying,
  currentTime,
  duration,
  videoRef,
  onSetVideoViewMode,
  onSetActiveZoneTab,
  onToggleCrosswalk,
  onResetZones,
  onSaveZones,
  onTogglePlay,
  onTimeUpdate,
  onSeek,
  onSvgPointerMove,
  onSvgPointerUp,
  onDragVertexStart,
  onDragOver,
  onDragLeave,
  onDrop,
  onUploadClick,
  onLoadSample,
}) => {
  return (
    <section className="canvas-card">
      <div className="canvas-toolbar">
        <div className="canvas-label">
          <ScanLine size={15} />
          <span>FEED: {selectedVideo ? baseVideoStem.toUpperCase() : 'NO VIDEO LOADED'}</span>
          {selectedVideo && (
            <div className="feed-toggle-pills" style={{ marginLeft: 8 }}>
              <Button
                className={`feed-toggle-btn ${videoViewMode === 'raw' ? 'active' : ''}`}
                onClick={() => onSetVideoViewMode('raw')}
              >
                RAW CCTV FEED
              </Button>
              <Button
                className={`feed-toggle-btn ${videoViewMode === 'analyzed' ? 'active' : ''}`}
                onClick={() => onSetVideoViewMode('analyzed')}
                title={annotatedVideoExists ? 'Switch to AI analyzed video' : 'Run render to generate annotated output'}
              >
                AI ANALYZED {annotatedVideoExists ? '●' : ''}
              </Button>
            </div>
          )}
        </div>

        <div className="canvas-actions">
          {selectedVideo && mode === 'edit' && (
            <>
              <div className="layer-tabs">
                <Button
                  className={`layer-tab-btn ${activeZoneTab === 'road' ? 'active-road' : ''}`}
                  onClick={() => onSetActiveZoneTab('road')}
                >
                  Road Polygon
                </Button>
                <Button
                  className={`layer-tab-btn ${activeZoneTab === 'crosswalk' ? 'active-crosswalk' : ''}`}
                  onClick={() => onSetActiveZoneTab('crosswalk')}
                >
                  Crosswalk
                </Button>
              </div>

              {activeZoneTab === 'crosswalk' && (
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#fcd34d', cursor: 'pointer', marginLeft: 4 }}>
                  <input
                    type="checkbox"
                    checked={crosswalkEnabled}
                    onChange={(e) => onToggleCrosswalk(e.target.checked)}
                    style={{ accentColor: '#fbbf24' }}
                  />
                  Enable Monitoring
                </label>
              )}

              <Button
                variant="icon"
                style={{
                  border: '1px solid #0284c7',
                  background: '#082f49',
                  color: '#38bdf8',
                  padding: '4px 8px',
                  fontSize: 10,
                  display: 'inline-flex',
                  gap: 5,
                  marginLeft: 6,
                }}
                onClick={onSaveZones}
                title="Save modified zone layout"
              >
                <Save size={13} /> Save Layout
              </Button>

              <Button
                variant="icon"
                style={{ border: '1px solid #26303c', padding: '4px 8px', fontSize: 10, display: 'inline-flex', gap: 5, marginLeft: 6 }}
                onClick={onResetZones}
                title="Reset zones to default layout"
              >
                <RotateCcw size={13} /> Reset Layout
              </Button>
            </>
          )}

          <Button
            variant="icon"
            aria-label="Fullscreen"
            onClick={() => {
              const el = document.querySelector('.feed-viewport')
              if (el && document.fullscreenElement) document.exitFullscreen()
              else if (el) el.requestFullscreen()
            }}
          >
            <Maximize2 size={15} />
          </Button>
        </div>
      </div>

      <div
        className={`feed-viewport ${!selectedVideo ? 'empty-dropzone' : ''} ${isDraggingOver ? 'drag-over' : ''}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {!selectedVideo ? (
          <div className="upload-empty-state">
            <div className="empty-upload-icon">
              <Upload size={32} style={{ color: '#38bdf8' }} />
            </div>
            <h3>Upload CCTV Video Stream</h3>
            <p>
              Drag &amp; drop your 4K/1080p MP4 or AVI footage here, or load the built-in intersection sample to calibrate zones and run safety checks.
            </p>
            <div className="empty-actions">
              <Button variant="primary" onClick={onUploadClick} disabled={isUploading}>
                {isUploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                {isUploading ? 'Uploading Video...' : 'Select Video File'}
              </Button>
              <Button variant="secondary" onClick={onLoadSample}>
                <Video size={14} style={{ color: '#38bdf8' }} />
                Load Default Sample (intersection_01.mp4)
              </Button>
            </div>
            <span style={{ fontSize: 10, color: '#475569', marginTop: 4 }}>
              Supports MP4, AVI, MOV up to 1GB · Zero predictions until you click &quot;Render Video&quot;
            </span>
          </div>
        ) : (
          <>
            <video
              key={currentStreamFile}
              ref={videoRef}
              src={getVideoStreamUrl(currentStreamFile)}
              className="video-player"
              playsInline
              muted
              onTimeUpdate={onTimeUpdate}
              onLoadedMetadata={onTimeUpdate}
              onClick={onTogglePlay}
              onError={(e) => {
                console.error(`Failed to load video stream: ${currentStreamFile}`, e)
              }}
            />

            <svg
              viewBox="0 0 3840 2160"
              className={`canvas-svg-overlay ${mode === 'edit' ? 'interactive' : ''}`}
              onPointerMove={onSvgPointerMove}
              onPointerUp={onSvgPointerUp}
              onPointerCancel={onSvgPointerUp}
            >
              {(mode === 'edit' || videoViewMode === 'raw' || !annotatedVideoExists) && zones?.road?.polygon && (
                <polygon
                  points={zones.road.polygon.map((p) => p.join(',')).join(' ')}
                  fill={mode === 'edit' && activeZoneTab === 'road' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(56, 189, 248, 0.05)'}
                  stroke="#38bdf8"
                  strokeWidth={mode === 'edit' && activeZoneTab === 'road' ? '8' : '4'}
                  strokeDasharray="16 8"
                />
              )}

              {(mode === 'edit' || videoViewMode === 'raw' || !annotatedVideoExists) && crosswalkEnabled && zones?.crosswalks?.[0]?.polygon && (
                <polygon
                  points={zones.crosswalks[0].polygon.map((p) => p.join(',')).join(' ')}
                  fill={mode === 'edit' && activeZoneTab === 'crosswalk' ? 'rgba(251, 191, 36, 0.25)' : 'rgba(251, 191, 36, 0.12)'}
                  stroke="#fbbf24"
                  strokeWidth={mode === 'edit' && activeZoneTab === 'crosswalk' ? '10' : '6'}
                />
              )}

              {mode === 'edit' && activeZoneTab === 'road' &&
                zones?.road?.polygon?.map(([x, y], idx) => (
                  <g key={`road-${idx}`}>
                    <circle
                      cx={x}
                      cy={y}
                      r="45"
                      fill="#0b1115"
                      stroke="#38bdf8"
                      strokeWidth="10"
                      style={{ cursor: 'grab' }}
                      onPointerDown={(e) => {
                        e.currentTarget.setPointerCapture(e.pointerId)
                        onDragVertexStart('road', idx)
                      }}
                      onPointerUp={(e) => {
                        try {
                          if (e.currentTarget.hasPointerCapture(e.pointerId)) {
                            e.currentTarget.releasePointerCapture(e.pointerId)
                          }
                        } catch {}
                        onSvgPointerUp()
                      }}
                    />
                    <text x={x + 52} y={y + 16} fill="#38bdf8" fontSize="48" fontFamily="monospace" fontWeight="bold">
                      R{idx + 1}
                    </text>
                  </g>
                ))}

              {mode === 'edit' && activeZoneTab === 'crosswalk' && crosswalkEnabled &&
                zones?.crosswalks?.[0]?.polygon?.map(([x, y], idx) => (
                  <g key={`cw-${idx}`}>
                    <circle
                      cx={x}
                      cy={y}
                      r="45"
                      fill="#0b1115"
                      stroke="#fbbf24"
                      strokeWidth="10"
                      style={{ cursor: 'grab' }}
                      onPointerDown={(e) => {
                        e.currentTarget.setPointerCapture(e.pointerId)
                        onDragVertexStart('crosswalk', idx)
                      }}
                      onPointerUp={(e) => {
                        try {
                          if (e.currentTarget.hasPointerCapture(e.pointerId)) {
                            e.currentTarget.releasePointerCapture(e.pointerId)
                          }
                        } catch {}
                        onSvgPointerUp()
                      }}
                    />
                    <text x={x + 52} y={y + 16} fill="#fbbf24" fontSize="48" fontFamily="monospace" fontWeight="bold">
                      P{idx + 1}
                    </text>
                  </g>
                ))}
            </svg>
          </>
        )}
      </div>

      {selectedVideo && (
        <VideoScrubber
          isPlaying={isPlaying}
          currentTime={currentTime}
          duration={duration}
          videoViewMode={videoViewMode}
          onTogglePlay={onTogglePlay}
          onSeek={onSeek}
        />
      )}

      {selectedVideo && mode === 'edit' && (
        <div className="edit-hint-bar">
          <span>EDIT MODE ACTIVE · Drag circular handles R1-R4 (Road) or P1-P4 (Crosswalk) to reshape zones</span>
          <span style={{ color: '#38bdf8' }}>Click &quot;Render Video&quot; to analyze with this layout</span>
        </div>
      )}

      <div className="canvas-footer">
        <div>
          <span className="legend-line" style={{ background: '#38bdf8' }} />
          <span>Road ROI ({zones?.road?.polygon?.length || 4} vertices)</span>
        </div>
        <div>
          <span className="legend-line" style={{ background: crosswalkEnabled ? '#fbbf24' : '#475569' }} />
          <span>{crosswalkEnabled ? 'Crosswalk Zone (Active)' : 'Crosswalk (Disabled)'}</span>
        </div>
        <div>
          <span className="legend-line" style={{ background: '#4ade80' }} />
          <span>Auto-Learned Trajectory Flow</span>
        </div>
        <div className="canvas-resolution">3840×2160 UHD · Native Coordinate Mapping</div>
      </div>
    </section>
  )
}

