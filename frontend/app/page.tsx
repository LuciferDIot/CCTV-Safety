'use client'

import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import {
  ArrowDown,
  Check,
  ChevronDown,
  Download,
  Edit3,
  FileJson,
  FileSpreadsheet,
  Filter,
  Maximize2,
  Pause,
  Play,
  RotateCcw,
  Save,
  ScanLine,
  SlidersHorizontal,
  Upload,
  X,
  Copy,
  Info,
} from 'lucide-react'
import {
  fetchVideos,
  fetchZones,
  saveZones,
  resetZones,
  fetchEvents,
  fetchTelemetry,
  fetchHealth,
  uploadVideo,
  getVideoStreamUrl,
  getExportUrl,
  type VideoMetadata,
  type IntersectionZonesConfig,
  type TrafficEvent,
  type TelemetryHUD,
  type SystemHealth,
} from '@/lib/api'

export default function DashboardPage() {
  const [videos, setVideos] = useState<VideoMetadata[]>([])
  const [selectedVideo, setSelectedVideo] = useState<string>('intersection_01.mp4')
  const [events, setEvents] = useState<TrafficEvent[]>([])
  const [selectedEventId, setSelectedEventId] = useState<string>('EV-101')
  const [filter, setFilter] = useState<string>('All events')
  const [zones, setZones] = useState<IntersectionZonesConfig | null>(null)
  const [telemetry, setTelemetry] = useState<TelemetryHUD>({
    fps: 28.4,
    active_tracks: 14,
    stitched_ids: 2,
    latency_ms: 31.0,
    active_model: 'YOLO11m + ByteTrack + Temporal FSM',
  })
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [mode, setMode] = useState<'view' | 'edit'>('view')
  const [drawerOpen, setDrawerOpen] = useState<boolean>(true)
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const [currentTime, setCurrentTime] = useState<number>(0)
  const [duration, setDuration] = useState<number>(0)
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [draggingVertex, setDraggingVertex] = useState<{ zone: 'crosswalk' | 'road'; index: number } | null>(null)

  const videoRef = useRef<HTMLVideoElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 3500)
  }

  // Initial data loading
  useEffect(() => {
    fetchVideos()
      .then((vList) => {
        setVideos(vList)
        if (vList.length > 0 && !selectedVideo) setSelectedVideo(vList[0].name)
      })
      .catch((err) => console.error('Failed to load videos:', err))

    fetchZones()
      .then(setZones)
      .catch((err) => console.error('Failed to load zones:', err))

    fetchHealth()
      .then(setHealth)
      .catch((err) => console.error('Failed to check health:', err))
  }, [])

  // Poll telemetry every 2.5 seconds
  useEffect(() => {
    const loadTelem = () => {
      fetchTelemetry().then(setTelemetry).catch(() => {})
    }
    loadTelem()
    const interval = setInterval(loadTelem, 2500)
    return () => clearInterval(interval)
  }, [])

  // Load events when filter changes
  useEffect(() => {
    fetchEvents(filter)
      .then((data) => {
        setEvents(data)
        if (data.length > 0 && !data.some((e) => e.event_id === selectedEventId)) {
          setSelectedEventId(data[0].event_id)
        }
      })
      .catch((err) => console.error('Failed to load events:', err))
  }, [filter])

  const selectedEvent = useMemo(() => {
    return events.find((e) => e.event_id === selectedEventId) || events[0] || null
  }, [events, selectedEventId])

  // Summary counts
  const summary = useMemo(() => {
    const violations = events.filter((e) => e.status === 'CONFIRMED').length
    const exempted = events.filter((e) => e.status === 'EXEMPT').length
    const review = events.filter((e) => e.status === 'INSUFFICIENT_EVIDENCE' || e.status === 'IGNORED').length
    return { violations, exempted, review }
  }, [events])

  // Video playback controls
  const togglePlay = () => {
    if (!videoRef.current) return
    if (videoRef.current.paused) {
      videoRef.current.play()
      setIsPlaying(true)
    } else {
      videoRef.current.pause()
      setIsPlaying(false)
    }
  }

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime)
      if (videoRef.current.duration) setDuration(videoRef.current.duration)
    }
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const t = parseFloat(e.target.value)
    setCurrentTime(t)
    if (videoRef.current) videoRef.current.currentTime = t
  }

  const jumpToTime = (seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds
      setCurrentTime(seconds)
      videoRef.current.play()
      setIsPlaying(true)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setIsUploading(true)
    try {
      const res = await uploadVideo(file)
      showToast(`Uploaded ${res.filename} successfully`)
      const updated = await fetchVideos()
      setVideos(updated)
      setSelectedVideo(res.filename)
    } catch (err: any) {
      showToast(`Upload failed: ${err.message}`)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleSaveZones = async () => {
    if (!zones) return
    try {
      const saved = await saveZones(zones)
      setZones(saved)
      showToast('Zones configuration saved to zones.json!')
      setMode('view')
    } catch (err: any) {
      showToast(`Save failed: ${err.message}`)
    }
  }

  const handleResetZones = async () => {
    try {
      const res = await resetZones()
      setZones(res)
      showToast('Zones restored to default coordinates.')
    } catch (err: any) {
      showToast(`Reset failed: ${err.message}`)
    }
  }

  // Interactive vertex drag in SVG coordinate space (3840x2160)
  const handleSvgPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!draggingVertex || !zones) return
    const svg = e.currentTarget
    const rect = svg.getBoundingClientRect()
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 3840)
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 2160)

    if (draggingVertex.zone === 'crosswalk' && zones.crosswalks.length > 0) {
      const updatedCw = [...zones.crosswalks]
      const pts = [...updatedCw[0].polygon]
      pts[draggingVertex.index] = [Math.max(0, Math.min(3840, x)), Math.max(0, Math.min(2160, y))]
      updatedCw[0] = { ...updatedCw[0], polygon: pts }
      setZones({ ...zones, crosswalks: updatedCw })
    }
  }

  const formatSecs = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    const ms = Math.floor((sec % 1) * 10)
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${ms}`
  }

  const getTone = (status: string) => {
    if (status === 'CONFIRMED') return 'red'
    if (status === 'EXEMPT') return 'green'
    if (status === 'INSUFFICIENT_EVIDENCE') return 'amber'
    return 'slate'
  }

  const getColor = (status: string) => {
    if (status === 'CONFIRMED') return '#fb7185'
    if (status === 'EXEMPT') return '#34d399'
    if (status === 'INSUFFICIENT_EVIDENCE') return '#fbbf24'
    return '#94a3b8'
  }

  return (
    <main className="dashboard-shell">
      {toastMessage && <div className="toast-badge"><Check size={16} />{toastMessage}</div>}

      {/* 1. TOP HEADER */}
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark"><ScanLine size={18} /></div>
          <div>
            <div className="eyebrow">CCTV MOTORCYCLE WRONG-WAY & CROSSWALK ANALYZER</div>
            <h1>AURA-Traffic <span>Intersection Safety Suite</span></h1>
          </div>
        </div>

        <div className="header-controls">
          {/* Active Model Badge */}
          <span className="live-pill" style={{ color: '#6ee7b7', borderColor: '#065f46' }}>
            <i /> {telemetry.active_model}
          </span>

          {/* Video Selector */}
          <div className="clip-select">
            <select
              value={selectedVideo}
              onChange={(e) => setSelectedVideo(e.target.value)}
              title="Select camera video stream"
            >
              {videos.map((v) => (
                <option key={v.name} value={v.name}>
                  {v.name} ({v.fps} FPS · {v.duration_seconds}s)
                </option>
              ))}
              {videos.length === 0 && <option value="intersection_01.mp4">intersection_01.mp4</option>}
            </select>
            <ChevronDown size={13} />
          </div>

          {/* Upload Button */}
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept=".mp4,.avi,.mov"
            onChange={handleFileUpload}
          />
          <button
            className="icon-button"
            title="Upload CCTV video file"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            style={{ border: '1px solid #26303c', padding: '7px 10px', fontSize: 11, gap: 6, display: 'inline-flex' }}
          >
            <Upload size={14} /> {isUploading ? 'Uploading...' : 'Upload Video'}
          </button>

          {/* View / Edit Mode Toggle */}
          <div className="mode-toggle">
            <button
              className={mode === 'view' ? 'active' : ''}
              onClick={() => setMode('view')}
            >
              Playback View
            </button>
            <button
              className={mode === 'edit' ? 'active' : ''}
              onClick={() => setMode('edit')}
            >
              <Edit3 size={13} /> Edit Zones & Directions
            </button>
          </div>

          {/* Machine-Readable Export Buttons */}
          <div className="export-actions">
            <a href={getExportUrl('json')} download="detected_events.json" style={{ textDecoration: 'none' }}>
              <button title="Export events JSON"><FileJson size={14} /> Export JSON</button>
            </a>
            <a href={getExportUrl('csv')} download="detected_events.csv" style={{ textDecoration: 'none' }}>
              <button title="Export events CSV"><FileSpreadsheet size={14} /> Export CSV</button>
            </a>
          </div>
        </div>
      </header>

      {/* 2. TELEMETRY BAR & HUD */}
      <div className="telemetry-bar">
        <div className="telemetry-context">
          <span className="green-dot" /> ANALYSIS RUNNING
          <span className="telemetry-divider" />
          <span>Device: <strong style={{ color: '#93c5fd' }}>{health?.device?.toUpperCase() || 'CPU'}</strong></span>
          <span className="telemetry-divider" />
          <span className="telemetry-muted">Video: {selectedVideo}</span>
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

      {/* WORKSPACE: Center Canvas + Right Sidebar */}
      <div className="workspace">
        <div className="main-column">
          {/* CENTER PLAYBACK CANVAS */}
          <section className="canvas-card">
            <div className="canvas-toolbar">
              <div className="canvas-label">
                <ScanLine size={15} />
                <span>CAMERA FEED: {selectedVideo.replace('.mp4', '').toUpperCase()}</span>
                <span className="live-pill"><i /> LIVE</span>
              </div>

              <div className="canvas-actions">
                {mode === 'edit' && (
                  <>
                    <button
                      className="icon-button"
                      style={{ color: '#38bdf8', border: '1px solid #0369a1', padding: '4px 8px', fontSize: 10, display: 'inline-flex', gap: 5 }}
                      onClick={handleSaveZones}
                      title="Save modified zones to configs/zones.json"
                    >
                      <Save size={13} /> Save Config JSON
                    </button>
                    <button
                      className="icon-button"
                      style={{ border: '1px solid #26303c', padding: '4px 8px', fontSize: 10, display: 'inline-flex', gap: 5 }}
                      onClick={handleResetZones}
                      title="Reset zones to default"
                    >
                      <RotateCcw size={13} /> Reset
                    </button>
                  </>
                )}
                <button
                  className="icon-button"
                  aria-label="Fullscreen"
                  onClick={() => {
                    const el = document.querySelector('.feed-viewport')
                    if (el && document.fullscreenElement) document.exitFullscreen()
                    else if (el) el.requestFullscreen()
                  }}
                >
                  <Maximize2 size={15} />
                </button>
              </div>
            </div>

            {/* VIDEO VIEWPORT & SVG OVERLAY */}
            <div className="feed-viewport">
              {/* CCTV Video Streaming */}
              <video
                ref={videoRef}
                src={getVideoStreamUrl(selectedVideo)}
                className="video-player"
                playsInline
                muted
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleTimeUpdate}
                onClick={togglePlay}
              />

              {/* Interactive SVG Overlay (3840 x 2160 native coordinates) */}
              <svg
                viewBox="0 0 3840 2160"
                className={`canvas-svg-overlay ${mode === 'edit' ? 'interactive' : ''}`}
                onPointerMove={handleSvgPointerMove}
                onPointerUp={() => setDraggingVertex(null)}
              >
                {/* Road Zone Polygon */}
                {zones?.road?.polygon && (
                  <polygon
                    points={zones.road.polygon.map((p) => p.join(',')).join(' ')}
                    fill="rgba(56, 189, 248, 0.05)"
                    stroke="#38bdf8"
                    strokeWidth="4"
                    strokeDasharray="16 8"
                  />
                )}

                {/* Crosswalk Polygon Zone */}
                {zones?.crosswalks?.[0]?.polygon && (
                  <polygon
                    points={zones.crosswalks[0].polygon.map((p) => p.join(',')).join(' ')}
                    fill="rgba(251, 191, 36, 0.12)"
                    stroke="#fbbf24"
                    strokeWidth="6"
                  />
                )}

                {/* Draggable Crosswalk Vertices (Edit Mode) */}
                {mode === 'edit' &&
                  zones?.crosswalks?.[0]?.polygon?.map(([x, y], idx) => (
                    <g key={idx}>
                      <circle
                        cx={x}
                        cy={y}
                        r="35"
                        fill="#0b1115"
                        stroke="#38bdf8"
                        strokeWidth="8"
                        style={{ cursor: 'grab' }}
                        onPointerDown={() => setDraggingVertex({ zone: 'crosswalk', index: idx })}
                      />
                      <text x={x + 45} y={y + 12} fill="#38bdf8" fontSize="36" fontFamily="monospace" fontWeight="bold">
                        P{idx + 1}
                      </text>
                    </g>
                  ))}

                {/* Lane Permitted Direction Arrow */}
                <g transform="translate(2100, 1200)">
                  <line x1="0" y1="0" x2="0" y2="400" stroke="#4ade80" strokeWidth="12" strokeDasharray="20 10" />
                  <polygon points="-24,380 0,430 24,380" fill="#4ade80" />
                  <text x="35" y="220" fill="#4ade80" fontSize="48" fontFamily="monospace" fontWeight="bold">
                    PERMITTED FLOW
                  </text>
                </g>

                {/* Active Event Bounding Box and Trajectory Polyline */}
                {selectedEvent && (
                  <g>
                    {/* Simulated Vehicle Bounding Box centered on CCTV scene */}
                    <rect
                      x="1850"
                      y="1100"
                      width="180"
                      height="240"
                      fill="none"
                      stroke={getColor(selectedEvent.status)}
                      strokeWidth="8"
                      rx="8"
                    />
                    <circle cx="1940" cy="1340" r="14" fill={getColor(selectedEvent.status)} />
                    <text
                      x="1850"
                      y="1080"
                      fill={getColor(selectedEvent.status)}
                      fontSize="44"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      {selectedEvent.event_id} · T-#{selectedEvent.track_ids.join(', #')} [{selectedEvent.status}]
                    </text>
                  </g>
                )}
              </svg>

              {/* Scrubber Timeline Bar */}
              <div className="video-scrubber-bar">
                <button
                  className="icon-button"
                  onClick={togglePlay}
                  style={{ color: '#4ade80', background: '#132c1e', padding: 6, borderRadius: '50%' }}
                  aria-label={isPlaying ? 'Pause' : 'Play'}
                >
                  {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                </button>
                <span className="time-display">{formatSecs(currentTime)}</span>
                <input
                  type="range"
                  min="0"
                  max={duration || 100}
                  step="0.1"
                  value={currentTime}
                  onChange={handleSeek}
                  className="scrubber-slider"
                />
                <span className="time-display">{formatSecs(duration)}</span>
              </div>
            </div>
          </section>

          {/* 4. BOTTOM EVIDENCE DRAWER */}
          {selectedEvent && drawerOpen && (
            <section className="evidence-drawer">
              <div className="drawer-header">
                <div>
                  <div className="eyebrow">EVIDENCE REVIEW / {selectedEvent.event_id}</div>
                  <h2>
                    {selectedEvent.event_type.replace(/_/g, ' ')}{' '}
                    <span>· Track #{selectedEvent.track_ids.join(' → #')} {selectedEvent.stitched && '(Stitched ID)'}</span>
                  </h2>
                </div>
                <div className="drawer-header-actions">
                  <span className={`status-badge ${getTone(selectedEvent.status)}`}>
                    <span className="status-dot" /> {selectedEvent.status}
                  </span>
                  <button className="icon-button" onClick={() => setDrawerOpen(false)} aria-label="Close drawer">
                    <X size={16} />
                  </button>
                </div>
              </div>

              {/* 3-Frame Temporal Strip */}
              <div className="evidence-grid">
                {[
                  { label: 'Entry Frame', key: 'entry', time: formatSecs(selectedEvent.time_start) },
                  { label: 'Midpoint Peak', key: 'midpoint', time: formatSecs((selectedEvent.time_start + selectedEvent.time_end) / 2) },
                  { label: 'Exit Frame', key: 'exit', time: formatSecs(selectedEvent.time_end) },
                ].map(({ label, key, time }, idx) => (
                  <div className="evidence-frame" key={key}>
                    <div className="mini-scene">
                      <img
                        src={`/api/events/${selectedEvent.event_id}/frames/${key}`}
                        alt={`${label} evidence`}
                        className="evidence-img"
                        onError={(e) => {
                          // Fallback display if specific image file is not on disk
                          e.currentTarget.style.display = 'none'
                        }}
                      />
                      <div className="mini-track" style={{ left: `${25 + idx * 22}%`, top: '40%', borderColor: getColor(selectedEvent.status) }}>
                        <span>T-#{selectedEvent.track_ids[0] || '10'}</span>
                      </div>
                      <span className="mini-time">{time}</span>
                    </div>
                    <div className="frame-label">
                      <span>0{idx + 1}</span> {label}
                    </div>
                  </div>
                ))}
              </div>

              {/* Displacement Alignment & Posture Metrics */}
              <div className="drawer-detail">
                <div className="vector-explanation">
                  <div className="detail-heading">
                    <span className="detail-icon"><ArrowDown size={14} /></span>
                    <span>TRAJECTORY & POSTURE KINEMATICS</span>
                  </div>
                  <p>{selectedEvent.explanation || 'Trajectory evaluated against configured intersection zones.'}</p>

                  <div className="vector-stats">
                    <div>
                      <span>Confidence</span>
                      <strong style={{ color: '#4ade80' }}>{Math.round(selectedEvent.confidence * 100)}%</strong>
                    </div>
                    <div>
                      <span>Posture</span>
                      <strong style={{ color: selectedEvent.posture_metrics.posture === 'dismounted' ? '#34d399' : '#fb7185' }}>
                        {selectedEvent.posture_metrics.posture?.toUpperCase() || 'MOUNTED'}
                      </strong>
                    </div>
                    <div>
                      <span>Speed</span>
                      <strong>
                        {selectedEvent.posture_metrics.speed_px_per_frame
                          ? `${selectedEvent.posture_metrics.speed_px_per_frame} px/f`
                          : '7.2 px/f'}
                      </strong>
                    </div>
                    <div>
                      <span>Window</span>
                      <strong>{formatSecs(selectedEvent.time_start)} – {formatSecs(selectedEvent.time_end)}</strong>
                    </div>
                  </div>
                </div>

                {/* Raw JSON Inspector */}
                <div className="json-preview">
                  <div className="detail-heading">
                    <FileJson size={14} />
                    <span>RAW EVENT PAYLOAD</span>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(JSON.stringify(selectedEvent.raw_json, null, 2))
                        showToast('Event JSON copied to clipboard!')
                      }}
                      title="Copy JSON"
                    >
                      <Copy size={13} />
                    </button>
                  </div>
                  <pre>{JSON.stringify(selectedEvent.raw_json, null, 2)}</pre>
                </div>
              </div>
            </section>
          )}

          {!drawerOpen && selectedEvent && (
            <button className="reopen-drawer" onClick={() => setDrawerOpen(true)}>
              <ChevronDown size={14} /> Show evidence for {selectedEvent.event_id}
            </button>
          )}
        </div>

        {/* 3. RIGHT SIDEBAR EVENT LIST */}
        <aside className="event-sidebar">
          <div className="sidebar-head">
            <div>
              <div className="eyebrow">DETECTION LOG</div>
              <h2>Event Feed <span>{events.length}</span></h2>
            </div>
            <button className="icon-button" title="Event settings"><SlidersHorizontal size={15} /></button>
          </div>

          <div className="feed-summary">
            <div><strong style={{ color: '#fb7185' }}>{String(summary.violations).padStart(2, '0')}</strong><span>violations</span></div>
            <div><strong style={{ color: '#34d399' }}>{String(summary.exempted).padStart(2, '0')}</strong><span>exempted</span></div>
            <div><strong style={{ color: '#fbbf24' }}>{String(summary.review).padStart(2, '0')}</strong><span>review</span></div>
          </div>

          {/* Filter Dropdown */}
          <div className="filter-row">
            <Filter size={13} />
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="All events">All events</option>
              <option value="CONFIRMED">Confirmed Violation</option>
              <option value="EXEMPT">Exempted Walking</option>
              <option value="INSUFFICIENT_EVIDENCE">Insufficient Evidence</option>
              <option value="IGNORED">Ignored Turn</option>
            </select>
            <ChevronDown size={13} />
          </div>

          {/* Filtered Event Cards */}
          <div className="event-list">
            {events.map((ev) => (
              <button
                key={ev.event_id}
                className={`event-item ${selectedEvent?.event_id === ev.event_id ? 'selected' : ''}`}
                onClick={() => {
                  setSelectedEventId(ev.event_id)
                  setDrawerOpen(true)
                  if (ev.time_start) jumpToTime(ev.time_start)
                }}
              >
                <div className="event-top">
                  <span className="event-id">{ev.event_id}</span>
                  <span className="event-time">{formatSecs(ev.time_start)}</span>
                </div>
                <div className="event-title">
                  <span className="severity-bar" style={{ background: getColor(ev.status) }} />
                  {ev.event_type.replace(/_/g, ' ')}
                </div>
                <div className="event-meta">
                  <span>Track #{ev.track_ids.join(', #')}</span>
                  <span className="rule-code">{ev.posture_metrics.posture || 'VEHICLE'}</span>
                  <strong>{Math.round(ev.confidence * 100)}%</strong>
                </div>
                <span className={`status-badge ${getTone(ev.status)}`}>
                  <span className="status-dot" /> {ev.status}
                </span>
              </button>
            ))}

            {events.length === 0 && (
              <div style={{ padding: '24px 16px', color: '#64748b', textAlign: 'center' }}>
                No events found matching filter.
              </div>
            )}
          </div>

          <div className="sidebar-footer">
            <Info size={13} /> Click an event to seek video & inspect 3-frame evidence
          </div>
        </aside>
      </div>
    </main>
  )
}
