import React, { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { Badge, Loading, ErrorState, formatEta } from '../components/Shared'
import { fetchOperationsPlan } from '../api/client'

const ACTION_ICONS = {
  vessel_risk:    '🚢',
  hotspot:        '🔥',
  berth_conflict: '🏗️',
  crane_shortage: '🔧',
  routing:        '🗺️',
}

const FILTER_OPTS = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
const TYPE_OPTS   = ['ALL', 'vessel_risk', 'hotspot', 'berth_conflict', 'crane_shortage', 'routing']

function PlanRow({ item }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <div
        className="plan-item"
        onClick={() => setOpen(!open)}
        style={{ cursor: 'pointer', gridTemplateColumns: '4px 44px 1fr auto' }}
      >
        <div className={`plan-stripe ${item.priority_level}`} />
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 18 }}>{ACTION_ICONS[item.action_type] || '•'}</div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 1 }}>
            {item.action_type.replace('_', ' ')}
          </div>
        </div>
        <div>
          <div className="plan-issue">{item.issue}</div>
          <div className="plan-action">
            {item.affected_vessel && <span style={{ fontWeight: 500 }}>{item.affected_vessel} · </span>}
            {item.area}
            {' · '}
            {formatEta(item.time_window_start)} – {new Date(item.time_window_end).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <Badge level={item.priority_level} />
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
            #{item.priority_rank} {open ? '▴' : '▾'}
          </div>
        </div>
      </div>
      {open && (
        <div style={{
          background: 'var(--surface2)',
          borderBottom: '1px solid var(--border)',
          padding: '12px 20px 14px 60px',
        }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>Recommended Action</div>
          <p style={{ fontSize: 13, color: 'var(--text)', marginBottom: 8 }}>
            {item.recommended_action}
          </p>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Reason</div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.reason}</p>
        </div>
      )}
    </>
  )
}

export default function Plan() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [levelFilter, setLevelFilter] = useState('ALL')
  const [typeFilter, setTypeFilter]   = useState('ALL')

  const load = () => {
    setLoading(true)
    setError(null)
    fetchOperationsPlan()
      .then(r => { setData(r.data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }
  useEffect(load, [])

  if (loading) return <Layout title="72-Hour Plan"><Loading /></Layout>
  if (error)   return <Layout title="72-Hour Plan"><ErrorState message={error} onRetry={load} /></Layout>

  const filtered = data.items.filter(item =>
    (levelFilter === 'ALL' || item.priority_level === levelFilter) &&
    (typeFilter  === 'ALL' || item.action_type    === typeFilter)
  )

  return (
    <Layout
      title="72-Hour Operations Plan"
      subtitle={`${data.total_items} action items · Generated ${new Date(data.generated_at).toLocaleTimeString()}`}
    >
      {/* Summary banner */}
      <div className={`notice-banner ${data.critical_items > 0 ? 'critical' : ''}`}
        style={data.critical_items > 0 ? { background: 'var(--critical-bg)', borderColor: '#fecaca', color: '#991b1b' } : {}}>
        <strong>Executive Summary:</strong> {data.executive_summary}
      </div>

      {/* Summary chips */}
      <div className="flex-row mb-4" style={{ flexWrap: 'wrap' }}>
        <span className="badge CRITICAL">{data.critical_items} Critical</span>
        <span className="badge HIGH">{data.high_items} High</span>
        <span className="badge info">{data.total_items} Total Items</span>
        <span className="text-muted text-sm">
          Plan horizon: {data.plan_horizon_hours}h · Ends {formatEta(data.plan_end)}
        </span>
      </div>

      {/* Filters */}
      <div className="flex-row mb-4" style={{ flexWrap: 'wrap', gap: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>Priority:</span>
        {FILTER_OPTS.map(l => (
          <button key={l} onClick={() => setLevelFilter(l)} style={{
            padding: '3px 10px', borderRadius: 12, border: '1px solid var(--border)', fontSize: 11,
            background: levelFilter === l ? 'var(--accent)' : 'var(--surface)',
            color: levelFilter === l ? 'white' : 'var(--text)',
            fontWeight: 600, cursor: 'pointer',
          }}>
            {l}
          </button>
        ))}
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginLeft: 8 }}>Type:</span>
        {TYPE_OPTS.map(t => (
          <button key={t} onClick={() => setTypeFilter(t)} style={{
            padding: '3px 10px', borderRadius: 12, border: '1px solid var(--border)', fontSize: 11,
            background: typeFilter === t ? 'var(--navy)' : 'var(--surface)',
            color: typeFilter === t ? 'white' : 'var(--text)',
            fontWeight: 600, cursor: 'pointer',
          }}>
            {t === 'ALL' ? 'ALL' : t.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Plan items */}
      <div className="card">
        {filtered.length === 0 ? (
          <div className="state-box">
            <div className="state-icon">✅</div>
            <p>No items match the selected filters.</p>
          </div>
        ) : (
          filtered.map(item => <PlanRow key={item.item_id} item={item} />)
        )}
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 12, textAlign: 'right' }}>
        Click any row to expand the recommended action and reason.
      </div>
    </Layout>
  )
}
