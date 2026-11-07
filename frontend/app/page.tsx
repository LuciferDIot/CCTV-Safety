'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  Check,
  ChevronDown,
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
  Upload,
  X,
  Copy,
  Info,
  Layers,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Eye,
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
  startPipelineJob,
  fetchPipelineStatus,
  cancelPipelineJob,
  getVideoStreamUrl,
  getExportUrl,
  type VideoMetadata,
  type IntersectionZonesConfig,
  type ZonePolygon,
  type TrafficEvent,
  type TelemetryHUD,
  type SystemHealth,
  type PipelineStatusResponse,
} from '@/lib/api'

export default function DashboardPage() {
  const [videos, setVideos] = useState<VideoMetadata[]>([])
  const [selectedVideo, setSelectedVideo] = useState<string>('intersection_01.mp4')
  const [events, setEvents] = useState<TrafficEvent[]>([])
  const [selectedEventId, setSelectedEventId] = useState<string>('EV-101')
  const [filter, setFilter] = useState<string>('All events')
  const [zones, setZones] = useState<IntersectionZonesConfig | null>(null)
  const [lastCrosswalk, setLastCrosswalk] = useState<ZonePolygon | null>(null)
  const [activeZoneTab, setActiveZoneTab] = useState<'road' | 'crosswalk'>('road')
  const [telemetry, setTelemetry] = useState<TelemetryHUD>({
    fps: 28.4,
    active_tracks: 14,
    stitched_ids: 2,
    latency_ms: 31.0,
    active_model: 'YOLO11m + ByteTrack + Temporal FSM',
  })
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [mode, setMode] = useState<'view' | 'edit'>('view')
  const [videoViewMode, setVideoViewMode] = useState<'raw' | 'analyzed'>('raw')
  const [renderPreset, setRenderPreset] = useState<'preview' | 'full'>('preview')
  const [activeTask, setActiveTask] = useState<PipelineStatusResponse | null>(null)
  const [drawerOpen, setDrawerOpen] = useState<boolean>(true)
  const [isPlaying, setIsPlaying] = useState<boolean>(false)
  const [currentTime, setCurrentTime] = useState<number>(0)
  const [duration, setDuration] = useState<number>(0)
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [draggingVertex, setDraggingVertex] = useState<{ zone: 'crosswalk' | 'road'; index: number } | null>(null)

  const videoRef = useRef<HTMLVideoElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 3500)
  }

  // Determine current video stream
  const baseVideoStem = selectedVideo.replace('_annotated.mp4', '').replace('.mp4', '')
  const annotatedVideoName = `${baseVideoStem}_annotated.mp4`
  const annotatedVideoExists = videos.some((v) => v.name === annotatedVideoName)

  const currentStreamFile = videoViewMode === 'analyzed' && annotatedVideoExists
    ? annotatedVideoName
    : selectedVideo

  const crosswalkEnabled = Boolean(zones && zones.crosswalks && zones.crosswalks.length > 0)
  const isRendering = activeTask?.status === 'running'

  // Initial data loading
  useEffect(() => {
    fetchVideos()
      .then((vList) => {
        setVideos(vList)
        if (vList.length > 0 && !selectedVideo) setSelectedVideo(vList[0].name)
      })
      .catch((err) => console.error('Failed to load videos:', err))

    fetchZones()
      .then((z) => {
        setZones(z)
        if (z.crosswalks && z.crosswalks.length > 0) {
          setLastCrosswalk(z.crosswalks[0])
        }
      })
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

  // Clean up poll interval on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [])

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
      setDuration(videoRef.current.duration || 0)
    }
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const target = parseFloat(e.target.value)
    if (videoRef.current) {
      videoRef.current.currentTime = target
      setCurrentTime(target)
    }
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
      setVideoViewMode('raw')
    } catch (err: any) {
      showToast(`Upload failed: ${err.message}`)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // Crosswalk enable/disable toggle
  const handleToggleCrosswalk = (enabled: boolean) => {
    if (!zones) return
    if (enabled) {
      const restored = lastCrosswalk || {
        id: 'crosswalk_top',
        polygon: [
          [3022, 351],
          [1292, 351],
          [1088, 675],
          [3304, 672],
        ],
      }
      setZones({ ...zones, crosswalks: [restored] })
      showToast('Crosswalk monitoring enabled')
    } else {
      if (zones.crosswalks && zones.crosswalks.length > 0) {
        setLastCrosswalk(zones.crosswalks[0])
      }
      setZones({ ...zones, crosswalks: [] })
      showToast('Crosswalk monitoring disabled')
    }
  }

  const handleSaveZones = async () => {
    if (!zones) return
    try {
      const saved = await saveZones(zones)
      setZones(saved)
      showToast('Zones configuration saved to configs/zones.json!')
      setMode('view')
    } catch (err: any) {
      showToast(`Save failed: ${err.message}`)
    }
  }

  const handleResetZones = async () => {
    try {
      const res = await resetZones()
      setZones(res)
      if (res.crosswalks && res.crosswalks.length > 0) {
        setLastCrosswalk(res.crosswalks[0])
      }
      showToast('Zones restored to default coordinates.')
    } catch (err: any) {
      showToast(`Reset failed: ${err.message}`)
    }
  }

  // Video Rendering Trigger
  const handleStartRender = async () => {
    if (isRendering) return
    try {
      const maxFr = renderPreset === 'preview' ? 100 : null
      const initialTask = await startPipelineJob(selectedVideo, maxFr)
      setActiveTask(initialTask)
      showToast(`Started rendering (${renderPreset === 'preview' ? 'Fast 100 frames' : 'Full video'})`)

      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
      pollTimerRef.current = setInterval(async () => {
        try {
          const status = await fetchPipelineStatus(initialTask.task_id)
          setActiveTask(status)
          if (status.status === 'completed') {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current)
            showToast('Video analysis complete! Switched to AI Analyzed view.')
            const updatedVideos = await fetchVideos()
            setVideos(updatedVideos)
            setVideoViewMode('analyzed')
            const updatedEvents = await fetchEvents(filter)
            setEvents(updatedEvents)
          } else if (status.status === 'failed' || status.status === 'cancelled') {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current)
            showToast(`Rendering ${status.status}: ${status.error || ''}`)
          }
        } catch {
          // ignore transient poll error
        }
      }, 450)
    } catch (err: any) {
      showToast(`Failed to start render: ${err.message}`)
    }
  }

  const handleCancelRender = async () => {
    if (!activeTask) return
    try {
      const res = await cancelPipelineJob(activeTask.task_id)
      setActiveTask(res)
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
      showToast('Render cancelled.')
    } catch (err: any) {
      showToast(`Cancel failed: ${err.message}`)
    }
  }

  // Interactive vertex drag in SVG coordinate space (3840x2160)
  const handleSvgPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!draggingVertex || !zones) return
    const svg = e.currentTarget
    const rect = svg.getBoundingClientRect()
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 3840)
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 2160)
    const clampedX = Math.max(0, Math.min(3840, x))
    const clampedY = Math.max(0, Math.min(2160, y))

    if (draggingVertex.zone === 'road' && zones.road?.polygon) {
      const updatedRoad = { ...zones.road }
      const pts = [...updatedRoad.polygon]
      pts[draggingVertex.index] = [clampedX, clampedY]
      updatedRoad.polygon = pts
      setZones({ ...zones, road: updatedRoad })
    } else if (draggingVertex.zone === 'crosswalk' && zones.crosswalks && zones.crosswalks.length > 0) {
      const updatedCw = [...zones.crosswalks]
      const pts = [...updatedCw[0].polygon]
      pts[draggingVertex.index] = [clampedX, clampedY]
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
              onChange={(e) => {
                setSelectedVideo(e.target.value)
                setVideoViewMode('raw')
              }}
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
            <Upload size={14} /> {isUploading ? 'Uploading...' : 'Upload'}
          </button>

          {/* Render Preset & Start Button */}
          <div className="clip-select" style={{ padding: '4px 6px' }}>
            <select
              value={renderPreset}
              onChange={(e) => setRenderPreset(e.target.value as any)}
              title="Select rendering frame limit"
              style={{ fontSize: 10, maxWidth: 130 }}
            >
              <option value="preview">Fast Preview (100 fr)</option>
              <option value="full">Full Video (All fr)</option>
            </select>
            <ChevronDown size={12} />
          </div>

          <button
            className="render-cta-btn"
            onClick={handleStartRender}
            disabled={isRendering}
            title="Trigger AI detection, ByteTrack tracking, and safety rule analysis"
          >
            {isRendering ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {isRendering ? 'Rendering...' : 'Render Video'}
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
              <Edit3 size={13} /> Edit Zones
            </button>
          </div>

          {/* Machine-Readable Export Buttons */}
          <div className="export-actions">
            <a href={getExportUrl('json')} download="detected_events.json" style={{ textDecoration: 'none' }}>
              <button title="Export events JSON"><FileJson size={14} /> JSON</button>
            </a>
            <a href={getExportUrl('csv')} download="detected_events.csv" style={{ textDecoration: 'none' }}>
              <button title="Export events CSV"><FileSpreadsheet size={14} /> CSV</button>
            </a>
          </div>
        </div>
      </header>

      {/* 2. TELEMETRY BAR & HUD */}
      <div className="telemetry-bar">
        <div className="telemetry-context">
          <span className="green-dot" /> SYSTEM ACTIVE
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
          {/* INLINE RENDERING PROGRESS BANNER */}
          {activeTask && (
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
                    <button className="progress-cancel-btn" onClick={handleCancelRender}>
                      <X size={12} /> Cancel Render
                    </button>
                  )}
                  {activeTask.status !== 'running' && (
                    <button className="icon-button" onClick={() => setActiveTask(null)} title="Dismiss banner">
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
          )}

          {/* CENTER PLAYBACK CANVAS */}
          <section className="canvas-card">
            <div className="canvas-toolbar">
              <div className="canvas-label">
                <ScanLine size={15} />
                <span>FEED: {baseVideoStem.toUpperCase()}</span>
                {/* Raw vs Analyzed Toggle */}
                <div className="feed-toggle-pills" style={{ marginLeft: 8 }}>
                  <button
                    className={`feed-toggle-btn ${videoViewMode === 'raw' ? 'active' : ''}`}
                    onClick={() => setVideoViewMode('raw')}
                  >
                    RAW CCTV FEED
                  </button>
                  <button
                    className={`feed-toggle-btn ${videoViewMode === 'analyzed' ? 'active' : ''}`}
                    onClick={() => {
                      if (!annotatedVideoExists) {
                        showToast(`No annotated video yet for ${selectedVideo}. Click 'Render Video' first.`)
                      }
                      setVideoViewMode('analyzed')
                    }}
                    title={annotatedVideoExists ? 'Switch to AI analyzed video with bounding boxes & HUD' : 'Run render to generate annotated output'}
                  >
                    AI ANALYZED {annotatedVideoExists ? '●' : ''}
                  </button>
                </div>
              </div>

              <div className="canvas-actions">
                {mode === 'edit' && (
                  <>
                    {/* Layer Tabs: Road vs Crosswalk */}
                    <div className="layer-tabs">
                      <button
                        className={`layer-tab-btn ${activeZoneTab === 'road' ? 'active-road' : ''}`}
                        onClick={() => setActiveZoneTab('road')}
                      >
                        Road Polygon
                      </button>
                      <button
                        className={`layer-tab-btn ${activeZoneTab === 'crosswalk' ? 'active-crosswalk' : ''}`}
                        onClick={() => setActiveZoneTab('crosswalk')}
                      >
                        Crosswalk
                      </button>
                    </div>

                    {/* Crosswalk Enable/Disable Toggle */}
                    {activeZoneTab === 'crosswalk' && (
                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#fcd34d', cursor: 'pointer', marginLeft: 4 }}>
                        <input
                          type="checkbox"
                          checked={crosswalkEnabled}
                          onChange={(e) => handleToggleCrosswalk(e.target.checked)}
                          style={{ accentColor: '#fbbf24' }}
                        />
                        Enable Monitoring
                      </label>
                    )}

                    <button
                      className="icon-button"
                      style={{ color: '#38bdf8', border: '1px solid #0369a1', padding: '4px 8px', fontSize: 10, display: 'inline-flex', gap: 5, marginLeft: 6 }}
                      onClick={handleSaveZones}
                      title="Save modified zones to configs/zones.json"
                    >
                      <Save size={13} /> Save Config
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
                key={currentStreamFile}
                ref={videoRef}
                src={getVideoStreamUrl(currentStreamFile)}
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
                    fill={mode === 'edit' && activeZoneTab === 'road' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(56, 189, 248, 0.05)'}
                    stroke="#38bdf8"
                    strokeWidth={mode === 'edit' && activeZoneTab === 'road' ? '8' : '4'}
                    strokeDasharray="16 8"
                  />
                )}

                {/* Crosswalk Polygon Zone (if enabled) */}
                {crosswalkEnabled && zones?.crosswalks?.[0]?.polygon && (
                  <polygon
                    points={zones.crosswalks[0].polygon.map((p) => p.join(',')).join(' ')}
                    fill={mode === 'edit' && activeZoneTab === 'crosswalk' ? 'rgba(251, 191, 36, 0.25)' : 'rgba(251, 191, 36, 0.12)'}
                    stroke="#fbbf24"
                    strokeWidth={mode === 'edit' && activeZoneTab === 'crosswalk' ? '10' : '6'}
                  />
                )}

                {/* Draggable Road Vertices (Edit Mode - Road Active) */}
                {mode === 'edit' && activeZoneTab === 'road' &&
                  zones?.road?.polygon?.map(([x, y], idx) => (
                    <g key={`road-${idx}`}>
                      <circle
                        cx={x}
                        cy={y}
                        r="38"
                        fill="#0b1115"
                        stroke="#38bdf8"
                        strokeWidth="9"
                        style={{ cursor: 'grab' }}
                        onPointerDown={() => setDraggingVertex({ zone: 'road', index: idx })}
                      />
                      <text x={x + 48} y={y + 14} fill="#38bdf8" fontSize="40" fontFamily="monospace" fontWeight="bold">
                        R{idx + 1}
                      </text>
                    </g>
                  ))}

                {/* Draggable Crosswalk Vertices (Edit Mode - Crosswalk Active) */}
                {mode === 'edit' && activeZoneTab === 'crosswalk' && crosswalkEnabled &&
                  zones?.crosswalks?.[0]?.polygon?.map(([x, y], idx) => (
                    <g key={`cw-${idx}`}>
                      <circle
                        cx={x}
                        cy={y}
                        r="38"
                        fill="#0b1115"
                        stroke="#fbbf24"
                        strokeWidth="9"
                        style={{ cursor: 'grab' }}
                        onPointerDown={() => setDraggingVertex({ zone: 'crosswalk', index: idx })}
                      />
                      <text x={x + 48} y={y + 14} fill="#fbbf24" fontSize="40" fontFamily="monospace" fontWeight="bold">
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

                {/* Active Event Bounding Box in raw view mode */}
                {selectedEvent && videoViewMode === 'raw' && (
                  <g>
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

              {/* VIDEO SCRUBBER BAR */}
              <div className="video-scrubber-bar">
                <button
                  onClick={togglePlay}
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
                  onChange={handleSeek}
                  className="scrubber-slider"
                  aria-label="Video scrubber"
                />

                <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#6ee7b7' }}>
                  {videoViewMode === 'analyzed' ? 'AI ANNOTATED STREAM' : 'RAW CCTV STREAM'}
                </span>
              </div>
            </div>

            {/* CANVAS FOOTER / LEGEND */}
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
                <span className="legend-line green" />
                <span>Permitted Flow Vector</span>
              </div>
              <div className="canvas-resolution">
                3840×2160 UHD · Native Coordinate Mapping
              </div>
            </div>
          </section>

          {/* 4. TEMPORAL EVIDENCE REVIEW DRAWER */}
          {drawerOpen ? (
            <section className="evidence-drawer">
              <div className="drawer-header">
                <div>
                  <div className="eyebrow">TEMPORAL EVIDENCE STRIP REVIEW</div>
                  <h2>
                    {selectedEvent ? selectedEvent.event_id : 'NO EVENT SELECTED'}{' '}
                    <span>
                      {selectedEvent
                        ? `· Track #${selectedEvent.track_ids.join(', #')} · ${selectedEvent.event_type}`
                        : ''}
                    </span>
                  </h2>
                </div>

                <div className="drawer-header-actions">
                  {selectedEvent && (
                    <span className={`status-badge ${getTone(selectedEvent.status)}`}>
                      <span className="status-dot" />
                      {selectedEvent.status}
                    </span>
                  )}
                  <button
                    className="icon-button"
                    onClick={() => setDrawerOpen(false)}
                    title="Minimize evidence drawer"
                  >
                    <X size={15} />
                  </button>
                </div>
              </div>

              {/* 3-FRAME TEMPORAL STRIP */}
              <div className="evidence-grid">
                <div className="evidence-frame">
                  {selectedEvent?.evidence.entry_frame_url ? (
                    <img
                      src={selectedEvent.evidence.entry_frame_url}
                      alt="Entry Frame"
                      className="evidence-img"
                    />
                  ) : (
                    <div className="mini-scene">
                      <div className="mini-road" />
                      <div className="mini-crosswalk" />
                      <div className="mini-track" style={{ left: '42%', top: '48%', borderColor: '#38bdf8' }}>
                        <span>T-14</span>
                      </div>
                      <div className="mini-time">t=0.0s</div>
                    </div>
                  )}
                  <div className="frame-label">
                    <span>ENTRY FRAME</span> · Ground Contact Point
                  </div>
                </div>

                <div className="evidence-frame">
                  {selectedEvent?.evidence.midpoint_peak_url ? (
                    <img
                      src={selectedEvent.evidence.midpoint_peak_url}
                      alt="Peak Evidence"
                      className="evidence-img"
                    />
                  ) : (
                    <div className="mini-scene">
                      <div className="mini-road" />
                      <div className="mini-crosswalk" />
                      <div className="mini-track" style={{ left: '50%', top: '50%', borderColor: getColor(selectedEvent?.status || '') }}>
                        <span>T-14</span>
                      </div>
                      <div className="mini-time">t=0.7s</div>
                    </div>
                  )}
                  <div className="frame-label">
                    <span>MIDPOINT / PEAK</span> · Violation Evaluation
                  </div>
                </div>

                <div className="evidence-frame">
                  {selectedEvent?.evidence.exit_frame_url ? (
                    <img
                      src={selectedEvent.evidence.exit_frame_url}
                      alt="Exit Frame"
                      className="evidence-img"
                    />
                  ) : (
                    <div className="mini-scene">
                      <div className="mini-road" />
                      <div className="mini-crosswalk" />
                      <div className="mini-track" style={{ left: '60%', top: '53%', borderColor: '#4ade80' }}>
                        <span>T-14</span>
                      </div>
                      <div className="mini-time">t=1.4s</div>
                    </div>
                  )}
                  <div className="frame-label">
                    <span>EXIT FRAME</span> · Trajectory Clearance
                  </div>
                </div>
              </div>

              {/* KINEMATIC & EXPLANATION DETAILS */}
              <div className="drawer-detail">
                <div className="vector-explanation">
                  <div className="detail-heading">
                    <span className="detail-icon"><Info size={11} /></span>
                    SAFETY VERIFICATION & TRAJECTORY EXPLANATION
                  </div>
                  <p>
                    {selectedEvent?.explanation ||
                      'Vehicle trajectory evaluated with homography perspective scaling. Heading vector sustained across temporal confirmation window.'}
                  </p>
                  <div className="vector-stats">
                    <div>
                      <span>Observed Angle</span>
                      <strong>
                        {selectedEvent?.metrics.angle_deg != null
                          ? `${selectedEvent.metrics.angle_deg.toFixed(1)}°`
                          : '168.4°'}
                      </strong>
                    </div>
                    <div>
                      <span>Rule Window</span>
                      <strong>
                        {selectedEvent?.metrics.rule_window || '180° ± 45°'}
                      </strong>
                    </div>
                    <div>
                      <span>Confidence</span>
                      <strong style={{ color: '#4ade80' }}>
                        {selectedEvent ? `${Math.round(selectedEvent.confidence * 100)}%` : '96%'}
                      </strong>
                    </div>
                    <div>
                      <span>Rider Posture</span>
                      <strong style={{ color: selectedEvent?.posture_metrics.posture === 'DISMOUNTED' ? '#34d399' : '#fb7185' }}>
                        {selectedEvent?.posture_metrics.posture || 'MOUNTED'}
                      </strong>
                    </div>
                  </div>
                </div>

                <div className="json-preview">
                  <div className="detail-heading">
                    <span>RAW EVENT AUDIT RECORD</span>
                    <button
                      onClick={() => {
                        if (selectedEvent) {
                          navigator.clipboard.writeText(JSON.stringify(selectedEvent.raw_json, null, 2))
                          showToast('Copied JSON audit record to clipboard!')
                        }
                      }}
                      title="Copy JSON to clipboard"
                    >
                      <Copy size={13} />
                    </button>
                  </div>
                  <pre>
                    {selectedEvent
                      ? JSON.stringify(selectedEvent.raw_json, null, 2)
                      : '// No event record selected'}
                  </pre>
                </div>
              </div>
            </section>
          ) : (
            <button
              className="reopen-drawer"
              onClick={() => setDrawerOpen(true)}
            >
              <Eye size={13} /> View 3-Frame Temporal Evidence Strip & Kinematics ({selectedEvent?.event_id})
            </button>
          )}
        </div>

        {/* 5. RIGHT SIDEBAR: LIVE EVENT FEED */}
        <aside className="event-sidebar">
          <div className="sidebar-head">
            <div>
              <div className="eyebrow">AUDIT RECORD FEED</div>
              <h2>
                Safety Events <span>{events.length}</span>
              </h2>
            </div>
            <button
              className="icon-button"
              title="Refresh event records"
              onClick={() => {
                fetchEvents(filter).then(setEvents).catch(console.error)
                showToast('Refreshed event feed.')
              }}
            >
              <RotateCcw size={14} />
            </button>
          </div>

          {/* SUMMARY BADGES */}
          <div className="feed-summary">
            <div>
              <strong style={{ color: '#fb7185' }}>{summary.violations}</strong>
              <span>Violations</span>
            </div>
            <div>
              <strong style={{ color: '#34d399' }}>{summary.exempted}</strong>
              <span>Exempted</span>
            </div>
            <div>
              <strong style={{ color: '#fbbf24' }}>{summary.review}</strong>
              <span>Review</span>
            </div>
          </div>

          {/* FILTER DROPDOWN */}
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

          {/* EVENT CARDS LIST */}
          <div className="event-list">
            {events.map((ev) => {
              const tone = getTone(ev.status)
              const isSelected = ev.event_id === selectedEventId
              return (
                <button
                  key={ev.event_id}
                  className={`event-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    setSelectedEventId(ev.event_id)
                    setDrawerOpen(true)
                    jumpToTime(ev.time_start)
                  }}
                >
                  <div className="event-top">
                    <span className="event-id">{ev.event_id}</span>
                    <span className="event-time">{formatSecs(ev.time_start)}</span>
                  </div>

                  <div className="event-title">
                    <span
                      className="severity-bar"
                      style={{ background: getColor(ev.status) }}
                    />
                    <span>{ev.event_type}</span>
                  </div>

                  <div className="event-meta">
                    <span className="rule-code">TRK-{ev.track_ids.join(',')}</span>
                    <span className={`status-badge ${tone}`}>
                      <span className="status-dot" />
                      {ev.status}
                    </span>
                    <strong>{Math.round(ev.confidence * 100)}%</strong>
                  </div>
                </button>
              )
            })}

            {events.length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>
                No events match filter &quot;{filter}&quot;
              </div>
            )}
          </div>

          <div className="sidebar-footer">
            <div className="green-dot" />
            <span>Temporal FSM Engine Connected</span>
          </div>
        </aside>
      </div>
    </main>
  )
}
