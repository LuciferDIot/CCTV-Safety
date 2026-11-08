'use client'

import React from 'react'
import { Info, Copy, X } from 'lucide-react'
import { Badge, getColor } from '@/components/atoms'
import type { TrafficEvent } from '@/lib/api'

interface EvidenceDrawerProps {
  selectedEvent: TrafficEvent | null
  imgErrors: Record<string, boolean>
  onClose: () => void
  onImageError: (key: string) => void
  onCopyJson: () => void
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  selectedEvent,
  imgErrors,
  onClose,
  onImageError,
  onCopyJson,
}) => {
  return (
    <section className="evidence-drawer">
      <div className="drawer-header">
        <div>
          <div className="eyebrow">TEMPORAL EVIDENCE STRIP REVIEW</div>
          <h2>
            {selectedEvent ? selectedEvent.event_id : 'NO EVENT SELECTED'}{' '}
            <span>
              {selectedEvent ? `· Track #${(selectedEvent.track_ids || []).join(', #')} · ${selectedEvent.event_type}` : ''}
            </span>
          </h2>
        </div>

        <div className="drawer-header-actions">
          {selectedEvent && <Badge status={selectedEvent.status} />}
          <button className="icon-button" onClick={onClose} title="Minimize evidence drawer">
            <X size={15} />
          </button>
        </div>
      </div>

      <div className="evidence-grid">
        <div className="evidence-frame">
          {selectedEvent?.evidence?.entry_frame_url && !imgErrors[`${selectedEvent.event_id}-entry`] ? (
            <img
              src={selectedEvent.evidence.entry_frame_url}
              alt="Entry Frame"
              className="evidence-img"
              onError={() => onImageError(`${selectedEvent.event_id}-entry`)}
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
          {(selectedEvent?.evidence?.midpoint_peak_url || selectedEvent?.evidence?.midpoint_frame_url) &&
          !imgErrors[`${selectedEvent.event_id}-midpoint`] ? (
            <img
              src={selectedEvent.evidence?.midpoint_peak_url || selectedEvent.evidence?.midpoint_frame_url || ''}
              alt="Peak Evidence"
              className="evidence-img"
              onError={() => onImageError(`${selectedEvent.event_id}-midpoint`)}
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
          {selectedEvent?.evidence?.exit_frame_url && !imgErrors[`${selectedEvent.event_id}-exit`] ? (
            <img
              src={selectedEvent.evidence.exit_frame_url}
              alt="Exit Frame"
              className="evidence-img"
              onError={() => onImageError(`${selectedEvent.event_id}-exit`)}
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

      <div className="drawer-detail">
        <div className="vector-explanation">
          <div className="detail-heading">
            <span className="detail-icon"><Info size={11} /></span>
            SAFETY VERIFICATION &amp; TRAJECTORY EXPLANATION
          </div>
          <p>
            {selectedEvent?.explanation ||
              'Vehicle trajectory evaluated with homography perspective scaling. Heading vector sustained across temporal confirmation window.'}
          </p>
          <div className="vector-stats">
            <div>
              <span>Observed Angle</span>
              <strong>
                {selectedEvent?.metrics?.angle_deg != null ? `${selectedEvent.metrics.angle_deg.toFixed(1)}°` : '168.4°'}
              </strong>
            </div>
            <div>
              <span>Rule Window</span>
              <strong>{selectedEvent?.metrics?.rule_window || '180° ± 45°'}</strong>
            </div>
            <div>
              <span>Confidence</span>
              <strong style={{ color: '#4ade80' }}>
                {selectedEvent ? `${Math.round(selectedEvent.confidence * 100)}%` : '96%'}
              </strong>
            </div>
            <div>
              <span>Rider Posture</span>
              <strong style={{ color: (selectedEvent?.posture_metrics?.posture || '').toUpperCase() === 'DISMOUNTED' ? '#34d399' : '#fb7185' }}>
                {(selectedEvent?.posture_metrics?.posture || 'MOUNTED').toUpperCase()}
              </strong>
            </div>
          </div>
        </div>

        <div className="json-preview">
          <div className="detail-heading">
            <span>RAW EVENT AUDIT RECORD</span>
            <button onClick={onCopyJson} title="Copy JSON to clipboard">
              <Copy size={13} />
            </button>
          </div>
          <pre>{selectedEvent ? JSON.stringify(selectedEvent.raw_json || selectedEvent, null, 2) : '// No event record selected'}</pre>
        </div>
      </div>
    </section>
  )
}

