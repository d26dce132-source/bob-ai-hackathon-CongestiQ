import React, { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { Badge, ScoreBar, Loading, ErrorState, formatEta } from '../components/Shared'
import { fetchCongestion, fetchHotspots } from '../api/client'

function WindowBars({ windows }) {
  const maxScore = Math.max(...windows.map(w => w.score), 1)
  return (
    <div>
      <div className="window-grid">
        {windows.map((w, i) => {
          const h = Math.round((w.score / maxScore) * 100)
          const label = new Date(w.window_start).toLocaleTimeString('en-GB', {
            hour: '2-digit', minute: '2-digit', hour12: false
          })
          return (
            <div key={i} className="window-col" title={`Score: ${w.score} | ${w.level}`}>
              <div className="window-bar-wrap">
                <div
                  className={`window-bar-fill ${w.level}`}
                  style={{ height: `${h}%` }}
                />
              </div>
              <div className="window-label">{label}</div>
            </div>
          )
        })}
      </div>
      <div className="flex-row mt-4" style={{ fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap', gap: 12 }}>
        {['LOW','MEDIUM','HIGH','CRITICAL'].map(l => (
          <span key={l} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{
              width: 10, height: 10, borderRadius: 2, display: 'inline-block',
              background: `var(--${l.toLowerCase()})`,
            }} />
            {l}
          </span>
        ))}
        <span>· Each bar = 6h window</span>
      </div>
    </div>
  )
}

function HotspotCard({ h }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="hotspot-card">
      <div
        className={`hotspot-header ${h.severity}`}
        style={{ cursor: 'pointer' }}
        onClick={() => setOpen(!open)}
      >
        <div>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{h.berth_code}</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>{h.terminal}</span>
        </div>
        <div className="flex-row">
          <ScoreBar score={h.hotspot_score} level={h.severity} />
          <Badge level={h.severity} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {h.scheduled_vessel_count} vessel(s) {open ? '▴' : '▾'}
          </span>
        </div>
      </div>
      {open && (
        <div className="hotspot-body">
          <div className="flex-row mb-4" style={{ flexWrap: 'wrap', gap: 8 }}>
            <span className="badge muted">Overlap: {h.overlap_hours}h</span>
            <span className="badge muted">Cranes needed: {h.required_crane_count}</span>
            <span className="badge muted">Cranes available: {h.available_crane_count}</span>
          </div>
          <div className="gap-8 mb-4">
            {h.reasons?.map((r, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--text)', display: 'flex', gap: 6 }}>
                <span style={{ color: 'var(--high)' }}>▸</span> {r}
              </div>
            ))}
          </div>
          {h.affected_vessels?.length > 0 && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6 }}>
                Affected Vessels
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Vessel</th>
                      <th>ETA</th>
                      <th>Delay</th>
                      <th>Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {h.affected_vessels.map(v => (
                      <tr key={v.vessel_id}>
                        <td style={{ fontWeight: 500 }}>{v.vessel_name}</td>
                        <td className="td-muted">{formatEta(v.eta)}</td>
                        <td className="td-muted">{v.delay_hours > 0 ? `+${v.delay_hours}h` : '—'}</td>
                        <td><span className="badge muted">P{v.priority}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Congestion() {
  const [congestion, setCongestion] = useState(null)
  const [hotspots, setHotspots]     = useState(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([fetchCongestion(), fetchHotspots()])
      .then(([c, h]) => {
        setCongestion(c.data)
        setHotspots(h.data)
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }
  useEffect(load, [])

  if (loading) return <Layout title="Congestion"><Loading /></Layout>
  if (error)   return <Layout title="Congestion"><ErrorState message={error} onRetry={load} /></Layout>

  return (
    <Layout
      title="Congestion Analysis"
      subtitle="72-hour prediction horizon · 6-hour rolling windows"
    >
      {/* Top row */}
      <div className="grid-2 mb-6">
        {/* Overall score */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">⚡ Port-Wide Congestion Score</div>
            <Badge level={congestion.overall_level} />
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
              <div className="gauge-wrap" style={{ padding: 0, minWidth: 120 }}>
                <div className={`gauge-circle ${congestion.overall_level}`}>
                  <span className="gauge-score">{congestion.overall_score?.toFixed(0)}</span>
                  <span className="gauge-label">{congestion.overall_level}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
                  Score / 100
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
                  {congestion.summary}
                </p>
                <div className="flex-row" style={{ flexWrap: 'wrap', gap: 8 }}>
                  <span className="badge muted">Peak: {congestion.peak_score?.toFixed(0)}/100</span>
                  {congestion.peak_window_start && (
                    <span className="badge muted">
                      Peak window: {formatEta(congestion.peak_window_start)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Factor breakdown */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Contributing Factors</div>
          </div>
          <div className="card-body">
            {congestion.factors?.map(f => (
              <div key={f.name} className="factor-row">
                <div>
                  <div className="factor-name">{f.name}</div>
                </div>
                <div>
                  <ScoreBar score={f.contribution * (100 / 35)} level={congestion.overall_level} />
                  <div className="factor-desc">{f.description}</div>
                </div>
                <div style={{ textAlign: 'right', fontSize: 12, fontWeight: 600 }}>
                  {f.contribution?.toFixed(1)} pts
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Window bars */}
      <div className="card mb-6">
        <div className="card-header">
          <div className="card-title">72-Hour Congestion Timeline</div>
          <span className="text-sm text-muted">12 × 6-hour windows from now</span>
        </div>
        <div className="card-body">
          {congestion.window_scores && <WindowBars windows={congestion.window_scores} />}
        </div>
      </div>

      {/* Hotspots */}
      <div className="section-heading">🔥 Congestion Hotspots ({hotspots.total_hotspots})</div>
      {hotspots.total_hotspots === 0 ? (
        <div className="card">
          <div className="state-box">
            <div className="state-icon">✅</div>
            <p>{hotspots.port_summary}</p>
          </div>
        </div>
      ) : (
        <>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>
            {hotspots.port_summary}
          </p>
          {hotspots.hotspots?.map(h => (
            <HotspotCard key={h.berth_code} h={h} />
          ))}
        </>
      )}
    </Layout>
  )
}
