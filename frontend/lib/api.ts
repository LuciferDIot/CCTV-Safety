export interface VideoMetadata {
  name: string
  fps: number
  total_frames: number
  duration_seconds: number
  width: number
  height: number
  size_mb: number
  stream_url: string
}

export interface ZonePolygon {
  id: string
  polygon: [number, number][]
}

export interface LaneZoneConfig {
  id: string
  polygon: [number, number][]
  permitted_direction_vector: [number, number]
}

export interface IntersectionZonesConfig {
  camera_id: string
  video_file: string
  fps: number
  perspective_scale_by_y?: {
    y_top: number
    y_bottom: number
    weight_top: number
    weight_bottom: number
  }
  road: {
    id: string
    polygon: [number, number][]
    warmup_frames: number
  }
  crosswalks: ZonePolygon[]
  lanes: LaneZoneConfig[]
  metadata?: Record<string, any>
}

export interface PostureMetrics {
  posture: string
  vertical_clearance?: number | null
  lateral_offset_px?: number | null
  speed_px_per_frame?: number | null
}

export interface EvidenceFrames {
  entry_frame_url?: string | null
  midpoint_peak_url?: string | null
  exit_frame_url?: string | null
  card_url?: string | null
}

export interface TrafficEvent {
  event_id: string
  status: 'CONFIRMED' | 'EXEMPT' | 'INSUFFICIENT_EVIDENCE' | 'IGNORED' | string
  event_type: string
  track_ids: number[]
  stitched: boolean
  start_frame: number
  end_frame: number
  time_start: number
  time_end: number
  duration_sec: number
  confidence: number
  posture_metrics: PostureMetrics
  evidence: EvidenceFrames
  metrics: Record<string, any>
  explanation?: string | null
  raw_json: Record<string, any>
}

export interface TelemetryHUD {
  fps: number
  active_tracks: number
  stitched_ids: number
  latency_ms: number
  active_model: string
}

export interface SystemHealth {
  status: string
  app: string
  device: string
  model_loaded: boolean
  model_path: string
  uptime_seconds: number
}

const API_BASE = '/api'

export async function fetchHealth(): Promise<SystemHealth> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`)
  return res.json()
}

export async function fetchVideos(): Promise<VideoMetadata[]> {
  const res = await fetch(`${API_BASE}/videos`)
  if (!res.ok) throw new Error(`Failed to list videos: ${res.statusText}`)
  return res.json()
}

export async function uploadVideo(file: File): Promise<{ message: string; filename: string; metadata: VideoMetadata }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/videos/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Upload failed')
  }
  return res.json()
}

export async function fetchZones(): Promise<IntersectionZonesConfig> {
  const res = await fetch(`${API_BASE}/config/zones`)
  if (!res.ok) throw new Error(`Failed to load zones: ${res.statusText}`)
  return res.json()
}

export async function saveZones(config: IntersectionZonesConfig): Promise<IntersectionZonesConfig> {
  const res = await fetch(`${API_BASE}/config/zones`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to save zones: ${res.statusText}`)
  return res.json()
}

export async function resetZones(): Promise<IntersectionZonesConfig> {
  const res = await fetch(`${API_BASE}/config/zones/reset`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to reset zones: ${res.statusText}`)
  return res.json()
}

export async function fetchEvents(status?: string): Promise<TrafficEvent[]> {
  const url = status && status !== 'All events' ? `${API_BASE}/events?status=${encodeURIComponent(status)}` : `${API_BASE}/events`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to load events: ${res.statusText}`)
  return res.json()
}

export async function fetchTelemetry(): Promise<TelemetryHUD> {
  const res = await fetch(`${API_BASE}/pipeline/telemetry`)
  if (!res.ok) throw new Error(`Failed to load telemetry: ${res.statusText}`)
  return res.json()
}

export function getExportUrl(format: 'json' | 'csv'): string {
  return `${API_BASE}/events/export/${format}`
}

export function getVideoStreamUrl(videoName: string): string {
  return `${API_BASE}/videos/${encodeURIComponent(videoName)}/stream`
}
