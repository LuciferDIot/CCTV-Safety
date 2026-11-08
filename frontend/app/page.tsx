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

  const baseVideoStem = selectedVideo ? selectedVideo.replace(/\.[^/.]+$/, '').replace(/^annotated_/, '').replace(/_annotated$/, '') : ''
  const isTaskAnnotated = Boolean(
    activeTask?.status === 'completed' &&
    activeTask?.output_video &&
    (activeTask.output_video.startsWith(baseVideoStem) || activeTask.output_video.includes(baseVideoStem))
  )
  const matchedAnnotated = (isTaskAnnotated && activeTask?.output_video)
    ? activeTask.output_video
    : (videos.find((v) => v.name === `${baseVideoStem}_annotated.mp4` || v.name === `annotated_${baseVideoStem}.mp4`)?.name || `${baseVideoStem}_annotated.mp4`)
  const annotatedVideoExists = Boolean(
    baseVideoStem && (
      isTaskAnnotated ||
      videos.some((v) => v.name === `${baseVideoStem}_annotated.mp4` || v.name === `annotated_${baseVideoStem}.mp4`)
    )
  )
  const currentStreamFile = videoViewMode === 'analyzed' && annotatedVideoExists ? matchedAnnotated : selectedVideo
  const crosswalkEnabled = Boolean(zones && zones.crosswalks && zones.crosswalks.length > 0)
  const isRendering = activeTask?.status === 'running'

  const currentVideoMeta = useMemo(() => {
    return videos.find((v) => v.name === selectedVideo)
  }, [videos, selectedVideo])
  const maxZoneX = zones?.road?.polygon ? Math.max(...zones.road.polygon.map((p) => p[0]), 0) : 0
  const maxZoneY = zones?.road?.polygon ? Math.max(...zones.road.polygon.map((p) => p[1]), 0) : 0
  const videoWidth = currentVideoMeta?.width || (maxZoneX > 1920 ? 3840 : 1920)
  const videoHeight = currentVideoMeta?.height || (maxZoneY > 1080 ? 2160 : 1080)

  useEffect(() => {
    fetchVideos().then((vids) => {
      setVideos(vids)
    }).catch(console.error)
    fetchHealth().then(setHealth).catch(console.error)
  }, [])

  useEffect(() => {
    const loadTelem = () => fetchTelemetry().then(setTelemetry).catch(() => { })
    loadTelem()
    const interval = setInterval(loadTelem, 2500)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!selectedVideo) {
      setEvents([])
      setSelectedEventId('')
      return
    }
    fetchEvents(filter, selectedVideo)
      .then((data) => {
        setEvents(data)
        if (data.length > 0 && !data.some((e) => e.event_id === selectedEventId)) {
          setSelectedEventId(data[0].event_id)
        } else if (data.length === 0) {
          setSelectedEventId('')
        }
      })
      .catch(console.error)
  }, [filter, selectedVideo])

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

  const createDefaultZonesForVideo = (videoName: string, w: number, h: number, fps: number = 30.0): IntersectionZonesConfig => {
    return {
      camera_id: `cam_${videoName.replace(/\.[^/.]+$/, '')}`,
      video_file: videoName,
      fps: fps,
      perspective_scale_by_y: { y_top: 0.1, y_bottom: 1.0, weight_top: 0.35, weight_bottom: 1.0 },
      road: {
        id: 'road',
        polygon: [
          [Math.round(0.18 * w), Math.round(0.15 * h)],
          [Math.round(0.82 * w), Math.round(0.15 * h)],
          [Math.round(0.88 * w), Math.round(0.85 * h)],
          [Math.round(0.12 * w), Math.round(0.85 * h)],
        ],
        warmup_frames: 40,
      },
      crosswalks: [
        {
          id: 'crosswalk_zone',
          polygon: [
            [Math.round(0.75 * w), Math.round(0.35 * h)],
            [Math.round(0.25 * w), Math.round(0.35 * h)],
            [Math.round(0.25 * w), Math.round(0.55 * h)],
            [Math.round(0.75 * w), Math.round(0.55 * h)],
          ],
        },
      ],
      lanes: [],
    }
  }

  const handleSelectVideo = async (videoName: string, metaParam?: VideoMetadata) => {
    setIsPlaying(false)
    setSelectedVideo(videoName)
    setActiveTask(null)
    setVideoViewMode('raw')
    setMode('edit')

    const meta = metaParam || videos.find((v) => v.name === videoName)
    const w = meta?.width || 1920
    const h = meta?.height || 1080
    const fps = meta?.fps || 30.0

    try {
      const existing = await fetchZones(videoName, w, h)
      const existingStem = existing?.video_file ? existing.video_file.replace(/\.[^/.]+$/, '').replace(/^annotated_/, '').replace(/_annotated$/, '') : ''
      const currentStem = videoName.replace(/\.[^/.]+$/, '').replace(/^annotated_/, '').replace(/_annotated$/, '')
      if (existing && (existing.video_file === videoName || existingStem === currentStem) && existing.road?.polygon?.length) {
        setZones(existing)
        if (existing.crosswalks && existing.crosswalks.length > 0) {
          setLastCrosswalk(existing.crosswalks[0])
        }
        showToast(`Loaded ${videoName}. Default safety zones calibrated for ${w}x${h}.`)
        return
      }
    } catch {}

    const defaultZones = createDefaultZonesForVideo(videoName, w, h, fps)
    setZones(defaultZones)
    if (defaultZones.crosswalks && defaultZones.crosswalks.length > 0) {
      setLastCrosswalk(defaultZones.crosswalks[0])
    }
    saveZones(defaultZones).catch(() => {})
    showToast(`Loaded ${videoName}. Default safety zones calibrated for ${w}x${h}.`)
  }

  const processUploadedFile = async (file: File) => {
    setIsUploading(true)
    setIsPlaying(false)
    try {
      const res = await uploadVideo(file)
      showToast(`Uploaded ${res.filename} successfully`)
      const updated = await fetchVideos()
      setVideos(updated)
      await handleSelectVideo(res.filename, res.metadata)
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

  const handleToggleCrosswalk = (enabled: boolean) => {
    if (!zones) return
    if (enabled) {
      const defaultPolygon: [number, number][] = [
        [Math.round(0.80 * videoWidth), Math.round(0.20 * videoHeight)],
        [Math.round(0.25 * videoWidth), Math.round(0.20 * videoHeight)],
        [Math.round(0.20 * videoWidth), Math.round(0.38 * videoHeight)],
        [Math.round(0.85 * videoWidth), Math.round(0.38 * videoHeight)],
      ]
      const restored = lastCrosswalk || {
        id: 'crosswalk_zone',
        polygon: defaultPolygon,
      }
      const updated = { ...zones, crosswalks: [restored] }
      setZones(updated)
      saveZones(updated).catch(() => {})
      showToast('Crosswalk monitoring enabled')
    } else {
      if (zones.crosswalks && zones.crosswalks.length > 0) {
        setLastCrosswalk(zones.crosswalks[0])
      }
      const updated = { ...zones, crosswalks: [] }
      setZones(updated)
      saveZones(updated).catch(() => {})
      showToast('Crosswalk monitoring disabled')
    }
  }

  const handleResetZones = async () => {
    if (!selectedVideo) return
    try {
      const resetLayout = await resetZones(selectedVideo, videoWidth, videoHeight)
      setZones(resetLayout)
      if (resetLayout.crosswalks && resetLayout.crosswalks.length > 0) {
        setLastCrosswalk(resetLayout.crosswalks[0])
      }
      showToast(`Zones reset to default coordinates for ${videoWidth}x${videoHeight}.`)
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
    setIsPlaying(false)
    if (videoRef.current) videoRef.current.pause()
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
            if (videoRef.current) {
              videoRef.current.load()
            }
            const updatedEvents = await fetchEvents(filter, selectedVideo)
            setEvents(updatedEvents)
            if (updatedEvents.length > 0) {
              setSelectedEventId(updatedEvents[0].event_id)
              setTimeout(() => {
                if (updatedEvents[0].time_start != null) {
                  jumpToTime(updatedEvents[0].time_start)
                }
              }, 600)
            }
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
    const x = Math.round(((e.clientX - rect.left) / rect.width) * videoWidth)
    const y = Math.round(((e.clientY - rect.top) / rect.height) * videoHeight)
    const clampedX = Math.max(0, Math.min(videoWidth, x))
    const clampedY = Math.max(0, Math.min(videoHeight, y))

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
          onSetMode={setMode}
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
          videoWidth={videoWidth}
          videoHeight={videoHeight}
          onSelectVideo={handleSelectVideo}
          onUploadClick={() => fileInputRef.current?.click()}
        />
      }
      evidenceDrawer={
        drawerOpen && selectedEvent ? (
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
        ) : selectedEvent ? (
          <ReopenDrawerButton
            eventId={selectedEvent?.event_id}
            onClick={() => setDrawerOpen(true)}
          />
        ) : undefined
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
            if (selectedVideo) {
              fetchEvents(filter, selectedVideo).then(setEvents).catch(console.error)
              showToast('Refreshed event feed.')
            }
          }}
        />
      }
    />
  )
}
