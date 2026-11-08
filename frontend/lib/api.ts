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
  aspect_ratio?: number | null
  vertical_extent_px?: number | null
  vertical_clearance?: number | null
  lateral_offset_px?: number | null
  speed_px_per_frame?: number | null
}

export interface EvidenceFrames {
  entry_frame_idx?: number
  midpoint_frame_idx?: number
  exit_frame_idx?: number
  entry_frame_url?: string | null
  midpoint_peak_url?: string | null
  midpoint_frame_url?: string | null
  exit_frame_url?: string | null
  card_url?: string | null
  evidence_card_url?: string | null
}

export interface TrafficEvent {
  event_id: string
  status: 'CONFIRMED' | 'EXEMPT' | 'INSUFFICIENT_EVIDENCE' | 'IGNORED' | string
  event_type: string
  tracking_id?: number
  track_ids: number[]
  stitched: boolean
  start_frame?: number
  end_frame?: number
  start_time?: number
  end_time?: number
  time_start: number
  time_end: number
  duration_seconds?: number
  duration_sec: number
  confidence: number
  displacement_vector?: [number, number] | number[]
  alignment_dot_product?: number
  permitted_flow_vector?: [number, number] | number[]
  posture_metrics: PostureMetrics
  evidence_frames?: EvidenceFrames
  evidence: EvidenceFrames
  metrics: Record<string, any>
  natural_language_explanation?: string | null
  explanation?: string | null
  raw_json: Record<string, any>
}

export function normalizeTrafficEvent(raw: any): TrafficEvent {
  if (!raw || typeof raw !== 'object') {
    return {
      event_id: 'EV-00',
      status: 'IGNORED',
      event_type: 'UNKNOWN',
      tracking_id: 0,
      track_ids: [],
      stitched: false,
      time_start: 0,
      time_end: 0,
      duration_sec: 0,
      confidence: 0,
      posture_metrics: { posture: 'MOUNTED', aspect_ratio: 1.45, vertical_extent_px: 210.0 },
      evidence: {},
      metrics: { angle_deg: 180.0, rule_window: '180° ± 45°' },
      raw_json: {},
    }
  }

  // Tracking IDs & aliases
  const rawTrackId = raw.tracking_id ?? raw.track_id
  const rawTrackIds: number[] = Array.isArray(raw.track_ids)
    ? raw.track_ids.map((id: any) => Number(id))
    : rawTrackId != null
    ? [Number(rawTrackId)]
    : []
  const trackingId = rawTrackId != null ? Number(rawTrackId) : (rawTrackIds[0] ?? 0)

  // Timestamps & aliases
  const timeStart = Number(raw.time_start ?? raw.start_time ?? 0)
  const timeEnd = Number(raw.time_end ?? raw.end_time ?? timeStart)
  const durationSec = Number(
    raw.duration_sec ?? raw.duration_seconds ?? (timeEnd - timeStart > 0 ? timeEnd - timeStart : 0)
  )

  // Explanation
  const explanation = raw.explanation ?? raw.natural_language_explanation ?? ''

  // Evidence URLs & frames
  const rawEv = raw.evidence || raw.evidence_frames || {}
  const eventId = String(raw.event_id || 'EV-00')
  const evidence: EvidenceFrames = {
    entry_frame_idx: rawEv.entry_frame_idx ?? 0,
    midpoint_frame_idx: rawEv.midpoint_frame_idx ?? 1,
    exit_frame_idx: rawEv.exit_frame_idx ?? 2,
    entry_frame_url: rawEv.entry_frame_url || (eventId ? `/api/events/${eventId}/evidence/entry` : null),
    midpoint_peak_url: rawEv.midpoint_peak_url || rawEv.midpoint_frame_url || (eventId ? `/api/events/${eventId}/evidence/midpoint` : null),
    midpoint_frame_url: rawEv.midpoint_frame_url || rawEv.midpoint_peak_url || (eventId ? `/api/events/${eventId}/evidence/midpoint` : null),
    exit_frame_url: rawEv.exit_frame_url || (eventId ? `/api/events/${eventId}/evidence/exit` : null),
    card_url: rawEv.card_url || rawEv.evidence_card_url || (eventId ? `/api/events/${eventId}/evidence/card` : null),
    evidence_card_url: rawEv.evidence_card_url || rawEv.card_url || (eventId ? `/api/events/${eventId}/evidence/card` : null),
  }

  // Posture metrics
  const rawPosture = raw.posture_metrics || {}
  const postureStr = String(rawPosture.posture || raw.posture || 'MOUNTED').toUpperCase()
  const postureMetrics: PostureMetrics = {
    posture: postureStr,
    aspect_ratio: rawPosture.aspect_ratio != null ? Number(rawPosture.aspect_ratio) : 1.45,
    vertical_extent_px: rawPosture.vertical_extent_px != null ? Number(rawPosture.vertical_extent_px) : 210.0,
    vertical_clearance: rawPosture.vertical_clearance != null ? Number(rawPosture.vertical_clearance) : null,
    lateral_offset_px: rawPosture.lateral_offset_px != null ? Number(rawPosture.lateral_offset_px) : null,
    speed_px_per_frame: rawPosture.speed_px_per_frame != null ? Number(rawPosture.speed_px_per_frame) : null,
  }

  // Metrics
  const metrics: Record<string, any> = { ...(raw.metrics || {}) }
  if (metrics.angle_deg == null && raw.alignment_dot_product != null) {
    const dot = Math.max(-1, Math.min(1, Number(raw.alignment_dot_product)))
    metrics.angle_deg = Math.round(Math.acos(dot) * (180 / Math.PI) * 10) / 10
  }
  if (metrics.angle_deg == null) {
    metrics.angle_deg = 180.0
  }
  if (!metrics.rule_window) {
    metrics.rule_window = '180° ± 45°'
  }

  // Raw JSON record
  const rawJson = raw.raw_json && typeof raw.raw_json === 'object' && Object.keys(raw.raw_json).length > 0
    ? raw.raw_json
    : raw

  return {
    event_id: eventId,
    status: String(raw.status || 'CONFIRMED').toUpperCase(),
    event_type: String(raw.event_type || 'WRONG_WAY'),
    tracking_id: trackingId,
    track_ids: rawTrackIds,
    stitched: Boolean(raw.stitched),
    start_frame: raw.start_frame != null ? Number(raw.start_frame) : undefined,
    end_frame: raw.end_frame != null ? Number(raw.end_frame) : undefined,
    start_time: timeStart,
    end_time: timeEnd,
    time_start: timeStart,
    time_end: timeEnd,
    duration_seconds: durationSec,
    duration_sec: durationSec,
    confidence: raw.confidence != null ? Number(raw.confidence) : 0.95,
    displacement_vector: raw.displacement_vector,
    alignment_dot_product: raw.alignment_dot_product != null ? Number(raw.alignment_dot_product) : -0.85,
    permitted_flow_vector: raw.permitted_flow_vector,
    posture_metrics: postureMetrics,
    evidence_frames: evidence,
    evidence,
    metrics,
    natural_language_explanation: explanation,
    explanation,
    raw_json: rawJson,
  }
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

export interface PipelineStatusResponse {
  task_id: string
  status: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled' | string
  progress_pct: number
  current_frame: number
  total_frames: number
  fps: number
  elapsed_seconds: number
  eta_seconds?: number | null
  events_detected: number
  output_video?: string | null
  error?: string | null
}

const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || '').replace(/\/$/, '')
const API_BASE = BACKEND_URL ? `${BACKEND_URL}/api` : '/api'

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

export async function uploadVideo(file: File): Promise<{ message: string; filename: string; metadata?: VideoMetadata }> {
  const formData = new FormData()
  formData.append('file', file)

  const isLocal = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  const defaultLocalUrl = 'http://127.0.0.1:8000/api/videos/upload'
  const directUrl = BACKEND_URL ? `${BACKEND_URL}/api/videos/upload` : (isLocal ? defaultLocalUrl : `${API_BASE}/videos/upload`)

  let res: Response
  try {
    res = await fetch(directUrl, { method: 'POST', body: formData })
  } catch {
    res = await fetch(`${API_BASE}/videos/upload`, { method: 'POST', body: formData })
  }

  if (!res.ok) {
    let errorMsg = `Upload failed (Status ${res.status})`
    try {
      const err = await res.json()
      errorMsg = err.detail || err.message || errorMsg
    } catch {
      const raw = await res.text().catch(() => '')
      if (raw) errorMsg = raw.slice(0, 160)
    }
    throw new Error(errorMsg)
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
  const data = await res.json()
  if (Array.isArray(data)) {
    return data.map(normalizeTrafficEvent)
  }
  return []
}

export async function fetchTelemetry(): Promise<TelemetryHUD> {
  const res = await fetch(`${API_BASE}/pipeline/telemetry`)
  if (!res.ok) throw new Error(`Failed to load telemetry: ${res.statusText}`)
  return res.json()
}

export async function startPipelineJob(
  videoName: string,
  maxFrames?: number | null,
  zones?: IntersectionZonesConfig | null
): Promise<PipelineStatusResponse> {
  const payload: Record<string, any> = {
    video_name: videoName,
    max_frames: maxFrames !== undefined && maxFrames !== null ? maxFrames : 0,
  }
  if (zones) payload.zones = zones
  const res = await fetch(`${API_BASE}/pipeline/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Failed to start pipeline: ${res.statusText}`)
  return res.json()
}

export async function fetchPipelineStatus(taskId: string): Promise<PipelineStatusResponse> {
  const res = await fetch(`${API_BASE}/pipeline/status/${encodeURIComponent(taskId)}`)
  if (!res.ok) throw new Error(`Failed to fetch status: ${res.statusText}`)
  return res.json()
}

export async function cancelPipelineJob(taskId: string): Promise<PipelineStatusResponse> {
  const res = await fetch(`${API_BASE}/pipeline/cancel/${encodeURIComponent(taskId)}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Failed to cancel pipeline: ${res.statusText}`)
  return res.json()
}

export function getExportUrl(format: 'json' | 'csv'): string {
  return `${API_BASE}/events/export/${format}`
}

export function getVideoStreamUrl(videoName: string): string {
  return `${API_BASE}/videos/${encodeURIComponent(videoName)}/stream`
}
