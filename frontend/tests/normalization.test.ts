import test from 'node:test'
import assert from 'node:assert'
import { normalizeTrafficEvent } from '../lib/api.ts'

test('normalizeTrafficEvent with backend FastAPI schema (tracking_id, start_time, duration_seconds)', () => {
  const backendRaw = {
    event_id: 'EV-101',
    status: 'CONFIRMED',
    event_type: 'WRONG_WAY',
    tracking_id: 14,
    start_time: 4.12,
    end_time: 6.85,
    duration_seconds: 2.73,
    confidence: 0.98,
    alignment_dot_product: -0.92,
    natural_language_explanation: 'Motorcycle travelling against flow direction on Lane 2',
    posture_metrics: {
      posture: 'mounted',
      aspect_ratio: 1.45,
      vertical_extent_px: 210.0,
    },
  }

  const normalized = normalizeTrafficEvent(backendRaw)

  // Tracking IDs
  assert.strictEqual(normalized.event_id, 'EV-101')
  assert.strictEqual(normalized.tracking_id, 14)
  assert.deepStrictEqual(normalized.track_ids, [14])
  assert.strictEqual(normalized.track_ids.join(','), '14')

  // Timestamps
  assert.strictEqual(normalized.time_start, 4.12)
  assert.strictEqual(normalized.time_end, 6.85)
  assert.strictEqual(normalized.duration_sec, 2.73)

  // Explanation
  assert.strictEqual(normalized.explanation, 'Motorcycle travelling against flow direction on Lane 2')

  // Posture
  assert.strictEqual(normalized.posture_metrics.posture, 'MOUNTED')

  // Evidence fallback URLs
  assert.ok(normalized.evidence)
  assert.strictEqual(normalized.evidence.entry_frame_url, '/api/events/EV-101/evidence/entry')
  assert.strictEqual(normalized.evidence.midpoint_peak_url, '/api/events/EV-101/evidence/midpoint')
  assert.strictEqual(normalized.evidence.exit_frame_url, '/api/events/EV-101/evidence/exit')

  // Metrics
  assert.ok(normalized.metrics.angle_deg > 0)
  assert.strictEqual(normalized.metrics.rule_window, '180° ± 45°')
})

test('normalizeTrafficEvent with frontend alias schema (track_ids array, time_start, explanation)', () => {
  const frontendData = {
    event_id: 'EV-102',
    status: 'EXEMPT',
    event_type: 'CROSSWALK_RIDING',
    track_ids: [22, 23],
    time_start: 12.0,
    time_end: 15.5,
    duration_sec: 3.5,
    confidence: 0.88,
    explanation: 'Rider dismounted and walking across crosswalk',
    posture_metrics: {
      posture: 'DISMOUNTED',
    },
    evidence: {
      entry_frame_url: '/static/entry.jpg',
      midpoint_peak_url: '/static/mid.jpg',
      exit_frame_url: '/static/exit.jpg',
    },
    metrics: {
      angle_deg: 92.5,
      rule_window: '90° ± 30°',
    },
  }

  const normalized = normalizeTrafficEvent(frontendData)

  assert.deepStrictEqual(normalized.track_ids, [22, 23])
  assert.strictEqual(normalized.track_ids.join(', #'), '22, #23')
  assert.strictEqual(normalized.time_start, 12.0)
  assert.strictEqual(normalized.time_end, 15.5)
  assert.strictEqual(normalized.duration_sec, 3.5)
  assert.strictEqual(normalized.posture_metrics.posture, 'DISMOUNTED')
  assert.strictEqual(normalized.evidence.entry_frame_url, '/static/entry.jpg')
  assert.strictEqual(normalized.metrics.angle_deg, 92.5)
})

test('normalizeTrafficEvent handles null / undefined / empty input safely without throwing', () => {
  const nullEvent = normalizeTrafficEvent(null)
  assert.strictEqual(nullEvent.event_id, 'EV-00')
  assert.deepStrictEqual(nullEvent.track_ids, [])
  assert.doesNotThrow(() => nullEvent.track_ids.join(','))
  assert.strictEqual(nullEvent.time_start, 0)
  assert.ok(nullEvent.evidence)
  assert.ok(nullEvent.metrics)

  const emptyEvent = normalizeTrafficEvent({})
  assert.strictEqual(emptyEvent.event_id, 'EV-00')
  assert.deepStrictEqual(emptyEvent.track_ids, [])
  assert.doesNotThrow(() => emptyEvent.track_ids.join(','))
})
