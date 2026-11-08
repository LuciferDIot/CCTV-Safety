'use client'

import React from 'react'
import { Filter, ChevronDown, RotateCcw } from 'lucide-react'
import { Badge, StatusDot, getColor } from '@/components/atoms'
import { formatSecs } from '@/components/molecules'
import type { TrafficEvent } from '@/lib/api'

interface EventsSidebarProps {
  events: TrafficEvent[]
  selectedEventId: string
  filter: string
  summary: { violations: number; exempted: number; review: number }
  onSelectEvent: (eventId: string, timeStart: number) => void
  onFilterChange: (f: string) => void
  onRefresh: () => void
}

export const EventsSidebar: React.FC<EventsSidebarProps> = ({
  events,
  selectedEventId,
  filter,
  summary,
  onSelectEvent,
  onFilterChange,
  onRefresh,
}) => {
  return (
    <aside className="event-sidebar">
      <div className="sidebar-head">
        <div>
          <div className="eyebrow">AUDIT RECORD FEED</div>
          <h2>
            Safety Events <span>{events.length}</span>
          </h2>
        </div>
        <button className="icon-button" title="Refresh event records" onClick={onRefresh}>
          <RotateCcw size={14} />
        </button>
      </div>

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

      <div className="filter-row">
        <Filter size={13} />
        <select value={filter} onChange={(e) => onFilterChange(e.target.value)}>
          <option value="All events">All events</option>
          <option value="CONFIRMED">Confirmed Violation</option>
          <option value="EXEMPT">Exempted Walking</option>
          <option value="INSUFFICIENT_EVIDENCE">Insufficient Evidence</option>
          <option value="IGNORED">Ignored Turn</option>
        </select>
        <ChevronDown size={13} />
      </div>

      <div className="event-list">
        {events.map((ev) => {
          const isSelected = ev.event_id === selectedEventId
          return (
            <button
              key={ev.event_id}
              className={`event-item ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelectEvent(ev.event_id, ev.time_start)}
            >
              <div className="event-top">
                <span className="event-id">{ev.event_id}</span>
                <span className="event-time">{formatSecs(ev.time_start)}</span>
              </div>

              <div className="event-title">
                <span className="severity-bar" style={{ background: getColor(ev.status) }} />
                <span>{ev.event_type}</span>
              </div>

              <div className="event-meta">
                <span className="rule-code">TRK-{(ev.track_ids || []).join(',')}</span>
                <Badge status={ev.status} />
                <strong>{Math.round(ev.confidence * 100)}%</strong>
              </div>
            </button>
          )
        })}

        {events.length === 0 && (
          <div style={{ padding: 24, textAlign: 'center', color: '#64748b', fontSize: 11, lineHeight: 1.6 }}>
            No events analyzed yet for this video.<br />
            Click <strong style={{ color: '#38bdf8' }}>&quot;Render Video&quot;</strong> above to start AI safety detection.
          </div>
        )}
      </div>

      <div className="sidebar-footer">
        <StatusDot />
        <span>Temporal FSM Engine Connected</span>
      </div>
    </aside>
  )
}

