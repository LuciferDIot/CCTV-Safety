'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { ScanLine } from 'lucide-react'
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
  type VideoMetadata,
  type IntersectionZonesConfig,
  type ZonePolygon,
  type TrafficEvent,
  type TelemetryHUD,
  type SystemHealth,
  type PipelineStatusResponse,
} from '@/lib/api'

import { Toast, ReopenDrawerButton } from '@/components/atoms'
import { TelemetryBar, ProgressBanner } from '@/components/molecules'
import { AppHeader, VideoPlayerCanvas, EvidenceDrawer, EventsSidebar } from '@/components/organisms'
import { DashboardLayout } from '@/components/templates'

export default function DashboardPage() {
  const [isMounted, setIsMounted] = useState<boolean>(false)
  const [videos, setVideos] = useState<VideoMetadata[]>([])
  const [selectedVideo, setSelectedVideo] = useState<string>('')
  const [isDraggingOver, setIsDraggingOver] = useState<boolean>(false)
  const [events, setEvents] = useState<TrafficEvent[]>([])
  const [selectedEventId, setSelectedEventId] = useState<string>('EV-01')
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
  const [imgErrors, setImgErrors] = useState<Record<string, boolean>>({})

  const videoRef = useRef<HTMLVideoElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 3500)
  }

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const baseVideoStem = selectedVideo ? selectedVideo.replace('_annotated.mp4', '').replace('.mp4', '') : ''
  const annotatedVideoName = baseVideoStem ? `${baseVideoStem}_annotated.mp4` : ''
  const annotatedVideoExists = Boolean(annotatedVideoName && videos.some((v) => v.name === annotatedVideoName))
  const currentStreamFile = videoViewMode === 'analyzed' && annotatedVideoExists ? annotatedVideoName : selectedVideo
  const crosswalkEnabled = Boolean(zones && zones.crosswalks && zones.crosswalks.length > 0)
  const isRendering = activeTask?.status === 'running'

  useEffect(() => {
    fetchVideos().then(setVideos).catch(console.error)
    fetchZones()
      .then((z) => {
        setZones(z)
        if (z.crosswalks && z.crosswalks.length > 0) setLastCrosswalk(z.crosswalks[0])
      })
      .catch(console.error)
    fetchHealth().then(setHealth).catch(console.error)
  }, [])

  useEffect(() => {
    const loadTelem = () => fetchTelemetry().then(setTelemetry).catch(() => {})
    loadTelem()
    const interval = setInterval(loadTelem, 2500)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    fetchEvents(filter)
      .then((data) => {
        setEvents(data)
        if (data.length > 0 && !data.some((e) => e.event_id === selectedEventId)) {
          setSelectedEventId(data[0].event_id)
        }
      })
      .catch(console.error)
  }, [filter])

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [])

  const selectedEvent = useMemo(() => {
    return events.find((e) => e.event_id === selectedEventId) || events[0] || null
  }, [events, selectedEventId])

  const summary = useMemo(() => {
    const violations = events.filter((e) => e.status === 'CONFIRMED').length
    const exempted = events.filter((e) => e.status === 'EXEMPT').length
    const review = events.filter((e) => e.status === 'INSUFFICIENT_EVIDENCE' || e.status === 'IGNORED').length
    return { violations, exempted, review }
  }, [events])

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

  const handleSelectVideo = async (videoName: string) => {
    setIsPlaying(false)
    setSelectedVideo(videoName)
    setVideoViewMode('raw')
    setMode('view')

    if (videoName.includes('intersection_01')) {
      try {
        const defaultZones = await resetZones()
        setZones(defaultZones)
        if (defaultZones.crosswalks && defaultZones.crosswalks.length > 0) {
          setLastCrosswalk(defaultZones.crosswalks[0])
        }
      } catch {
        // fallback
      }
    } else {
      // For any new or other video (e.g. intersection_02, intersection_03, or uploaded videos):
      // Road boundary covers general scene; crosswalk is disabled by default (crosswalks: [])
      // so no phantom crosswalk is displayed where none exists in the scene.
      setZones({
        camera_id: `cam_${videoName.replace(/\.[^/.]+$/, '')}`,
        video_file: videoName,
        fps: 30.0,
        perspective_scale_by_y: { y_top: 0.1, y_bottom: 1.0, weight_top: 0.35, weight_bottom: 1.0 },
        road: {
          id: 'road',
          polygon: [
            [500, 200],
            [3340, 200],
            [3840, 2160],
            [0, 2160],
          ],
          warmup_frames: 40,
        },
        crosswalks: [],
        lanes: [],
      })
    }
    showToast(`Loaded ${videoName}. Ready for safety analysis.`)
  }

  const processUploadedFile = async (file: File) => {
    setIsUploading(true)
    setIsPlaying(false)
    try {
      const res = await uploadVideo(file)
      showToast(`Uploaded ${res.filename} successfully`)
      const updated = await fetchVideos()
      setVideos(updated)
      await handleSelectVideo(res.filename)
    } catch (err: any) {
      showToast(`Upload failed: ${err.message}`)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) await processUploadedFile(file)
  }

  const handleLoadSample = () => {
    handleSelectVideo('intersection_01.mp4')
  }

  const handleToggleCrosswalk = (enabled: boolean) => {
    if (!zones) return
    if (enabled) {
      const isSample1 = selectedVideo.includes('intersection_01')
      const defaultPolygon: [number, number][] = isSample1
        ? [
            [3022, 351],
            [1292, 351],
            [1088, 675],
            [3304, 672],
          ]
        : [
            [1000, 500],
            [2800, 500],
            [2800, 850],
            [1000, 850],
          ]
      const restored = lastCrosswalk && isSample1 ? lastCrosswalk : {
        id: 'crosswalk_zone',
        polygon: defaultPolygon,
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

  const handleResetZones = async () => {
    try {
      if (selectedVideo.includes('intersection_01')) {
        const res = await resetZones()
        setZones(res)
        if (res.crosswalks && res.crosswalks.length > 0) setLastCrosswalk(res.crosswalks[0])
        showToast('Zones restored to default coordinates.')
      } else {
        setZones({
          camera_id: `cam_${selectedVideo.replace(/\.[^/.]+$/, '')}`,
          video_file: selectedVideo,
          fps: 30.0,
          perspective_scale_by_y: { y_top: 0.1, y_bottom: 1.0, weight_top: 0.35, weight_bottom: 1.0 },
          road: {
            id: 'road',
            polygon: [
              [500, 200],
              [3340, 200],
              [3840, 2160],
              [0, 2160],
            ],
            warmup_frames: 40,
          },
          crosswalks: [],
          lanes: [],
        })
        showToast('Zones reset to clean corridor layout.')
      }
    } catch (err: any) {
      showToast(`Reset failed: ${err.message}`)
    }
  }

  const handleSaveZones = async () => {
    if (!zones) return
    try {
      const updated = await saveZones(zones)
      setZones(updated)
      showToast('Zone layout saved successfully!')
    } catch (err: any) {
      showToast(`Failed to save zones: ${err?.message || 'Unknown error'}`)
    }
  }

  const handleStartRender = async () => {
    if (isRendering || !selectedVideo) return
    try {
      const maxFr = renderPreset === 'preview' ? 100 : 0
      const initialTask = await startPipelineJob(selectedVideo, maxFr, zones)
      setActiveTask(initialTask)
      showToast(`Started rendering (${renderPreset === 'preview' ? 'Fast 100 frames' : 'Full video'})`)

      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
      let consecutiveErrors = 0
      pollTimerRef.current = setInterval(async () => {
        try {
          const status = await fetchPipelineStatus(initialTask.task_id)
          consecutiveErrors = 0
          setActiveTask(status)
          if (status.status === 'completed') {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current)
            showToast('Video analysis complete! Switched to AI Analyzed view.')
            const updatedVideos = await fetchVideos()
            setVideos(updatedVideos)
            setVideoViewMode('analyzed')
            setMode('view')
            const updatedEvents = await fetchEvents(filter)
            setEvents(updatedEvents)
            setTimeout(() => {
              if (updatedEvents.length > 0 && updatedEvents[0].time_start != null) {
                jumpToTime(updatedEvents[0].time_start)
              }
            }, 600)
          } else if (status.status === 'failed' || status.status === 'cancelled') {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current)
            showToast(`Rendering ${status.status}: ${status.error || ''}`)
          }
        } catch (err: any) {
          consecutiveErrors += 1
          const msg = String(err?.message || '')
          if (consecutiveErrors >= 3 || msg.includes('404') || msg.includes('Not Found')) {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current)
            setActiveTask(null)
            showToast('Render task interrupted or server reloaded. Please start again.')
          }
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

  if (!isMounted) {
    return (
      <main className="dashboard-shell" style={{ minHeight: '100vh', background: '#090c11' }}>
        <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', color: '#64748b', fontSize: 13, gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ScanLine size={20} style={{ color: '#4ade80' }} />
            <span>Initializing AURA-Traffic Intersection Safety Suite...</span>
          </div>
        </div>
      </main>
    )
  }

  return (
    <DashboardLayout
      toast={<Toast message={toastMessage} />}
      header={
        <AppHeader
          telemetry={telemetry}
          selectedVideo={selectedVideo}
          renderPreset={renderPreset}
          isRendering={isRendering}
          mode={mode}
          isUploading={isUploading}
          fileInputRef={fileInputRef}
          onSelectRenderPreset={setRenderPreset}
          onStartRender={handleStartRender}
          onSetMode={setMode}
          onSwitchVideo={() => {
            setIsPlaying(false)
            setSelectedVideo('')
            setVideoViewMode('raw')
            setMode('view')
          }}
          onUploadClick={() => fileInputRef.current?.click()}
          onFileUpload={handleFileUpload}
        />
      }
      telemetry={<TelemetryBar telemetry={telemetry} health={health} selectedVideo={selectedVideo} />}
      progressBanner={
        activeTask ? (
          <ProgressBanner
            activeTask={activeTask}
            onCancel={handleCancelRender}
            onDismiss={() => setActiveTask(null)}
          />
        ) : undefined
      }
      canvas={
        <VideoPlayerCanvas
          selectedVideo={selectedVideo}
          currentStreamFile={currentStreamFile}
          baseVideoStem={baseVideoStem}
          annotatedVideoExists={annotatedVideoExists}
          videoViewMode={videoViewMode}
          mode={mode}
          activeZoneTab={activeZoneTab}
          crosswalkEnabled={crosswalkEnabled}
          zones={zones}
          draggingVertex={draggingVertex}
          isDraggingOver={isDraggingOver}
          isUploading={isUploading}
          isPlaying={isPlaying}
          currentTime={currentTime}
          duration={duration}
          videoRef={videoRef}
          onSetVideoViewMode={setVideoViewMode}
          onSetActiveZoneTab={setActiveZoneTab}
          onToggleCrosswalk={handleToggleCrosswalk}
          onResetZones={handleResetZones}
          onSaveZones={handleSaveZones}
          onTogglePlay={togglePlay}
          onTimeUpdate={handleTimeUpdate}
          onSeek={handleSeek}
          onSvgPointerMove={handleSvgPointerMove}
          onSvgPointerUp={() => setDraggingVertex(null)}
          onDragVertexStart={(zone, index) => setDraggingVertex({ zone, index })}
          onDragOver={(e) => {
            e.preventDefault()
            e.stopPropagation()
            setIsDraggingOver(true)
          }}
          onDragLeave={(e) => {
            e.preventDefault()
            e.stopPropagation()
            setIsDraggingOver(false)
          }}
          onDrop={async (e) => {
            e.preventDefault()
            e.stopPropagation()
            setIsDraggingOver(false)
            if (e.dataTransfer.files?.length > 0) {
              await processUploadedFile(e.dataTransfer.files[0])
            }
          }}
          availableVideos={videos}
          onSelectVideo={handleSelectVideo}
          onUploadClick={() => fileInputRef.current?.click()}
          onLoadSample={handleLoadSample}
        />
      }
      evidenceDrawer={
        drawerOpen ? (
          <EvidenceDrawer
            selectedEvent={selectedEvent}
            imgErrors={imgErrors}
            onClose={() => setDrawerOpen(false)}
            onImageError={(key) => setImgErrors((prev) => ({ ...prev, [key]: true }))}
            onCopyJson={async () => {
              if (selectedEvent) {
                try {
                  const jsonStr = JSON.stringify(selectedEvent.raw_json || selectedEvent, null, 2)
                  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
                    await navigator.clipboard.writeText(jsonStr)
                    showToast('Copied JSON audit record to clipboard!')
                  } else {
                    showToast('Clipboard API not available')
                  }
                } catch (err: any) {
                  showToast(`Failed to copy: ${err?.message || 'Permission denied'}`)
                }
              }
            }}
          />
        ) : (
          <ReopenDrawerButton
            eventId={selectedEvent?.event_id}
            onClick={() => setDrawerOpen(true)}
          />
        )
      }
      sidebar={
        <EventsSidebar
          events={events}
          selectedEventId={selectedEventId}
          filter={filter}
          summary={summary}
          onSelectEvent={(id, t) => {
            setSelectedEventId(id)
            setDrawerOpen(true)
            jumpToTime(t)
          }}
          onFilterChange={setFilter}
          onRefresh={() => {
            fetchEvents(filter).then(setEvents).catch(console.error)
            showToast('Refreshed event feed.')
          }}
        />
      }
    />
  )
}
