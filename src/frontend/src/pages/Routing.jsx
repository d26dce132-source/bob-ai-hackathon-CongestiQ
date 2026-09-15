import React, { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { Badge, Loading, ErrorState, formatEta } from '../components/Shared'
import { fetchRouting } from '../api/client'

const ACTION_ICONS = {
  speed_reduction:    '🐢',
  anchor_and_wait:    '⚓',
  terminal_transfer:  '↔️',
  divert_to_anchorage:'🚨',
}

function RoutingCard({ rec }) {
  const [open, setOpen] = useState(true)
  const best = rec.alternatives?.reduce(
    (a, b) => b.feasibility_score > a.feasibility_score ? b : a,
    rec.alternatives[0]
  )

  return (
    <div className="routing-card">
      <div className="routing-card-header" onClick={() => setOpen(!open)} style={{ cursor: 'pointer' }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{rec.vessel_name}</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 10 }}>
            {rec.vessel_type?.replace('_', ' ')}
          </span>
          {rec.assigned_berth_code && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 10 }}>
              → {rec.assigned_berth_code}
            </span>
          )}
          {rec.eta && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 10 }}>
              ETA {formatEta(rec.eta)}
            </span>
          )}
        </div>
        <div className="flex-row">
          <Badge level={rec.current_risk_level} />
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Score {rec.current_risk_score?.toFixed(0)} {open ? '▴' : '▾'}
          </span>
        </div>
      </div>

      {open && (
        <>
          {/* Congestion driver */}
          <div style={{ padding: '10px 16px', background: 'var(--surface2)', borderBottom: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)' }}>
            <strong>Congestion driver:</strong> {rec.congestion_driver}
          </div>

          {/* Best recommendation */}
          <div style={{ padding: '10px 16px', background: '#eff6ff', borderBottom: '1px solid #bfdbfe', fontSize: 13 }}>
            <strong>Recommended action:</strong>{' '}
            <span style={{ color: 'var(--accent)' }}>{rec.recommended_action}</span>
          </div>

          {/* Alternatives */}
          {rec.alternatives?.map((alt, i) => (
            <div key={i} className="routing-alt">
              <div className="routing-rank">{alt.option_rank}</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>
                  {ACTION_ICONS[alt.action_type] || '→'} {alt.action_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text)', marginBottom: 4 }}>
                  {alt.description}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  ⚖️ {alt.trade_offs}
                </div>
                <div className="flex-row mt-4" style={{ flexWrap: 'wrap', gap: 6 }}>
                  <span className="badge muted">+{alt.estimated_delay_hours}h delay</span>
                  <span className="badge muted">{alt.congestion_reduction_pct}% congestion relief</span>
                </div>
              </div>
              <div style={{ textAlign: 'right', minWidth: 80 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Feasibility</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: alt.feasibility_score >= 60 ? 'var(--low)' : alt.feasibility_score >= 40 ? 'var(--medium)' : 'var(--critical)' }}>
                  {alt.feasibility_score?.toFixed(0)}
                </div>
              </div>
            </div>
          ))}

          {/* Data notice */}
          <div style={{ padding: '8px 16px', background: 'var(--surface2)', fontSize: 11, color: 'var(--text-muted)', borderTop: '1px solid var(--border)' }}>
            ℹ️ {rec.data_notice}
          </div>
        </>
      )}
    </div>
  )
}

export default function Routing() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchRouting()
      .then(r => { setData(r.data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }
  useEffect(load, [])

  if (loading) return <Layout title="Routing"><Loading /></Layout>
  if (error)   return <Layout title="Routing"><ErrorState message={error} onRetry={load} /></Layout>

  return (
    <Layout
      title="Alternative Routing Recommendations"
      subtitle={`${data.total_vessels_affected} vessel(s) at significant risk · based on simulated port data`}
    >
      <div className="notice-banner">
        ℹ️ {data.recommendations[0]?.data_notice || 'Routing recommendations are based on simulated port operational data and are for prototype demonstration purposes.'}
      </div>

      <div className="flex-row mb-4">
        <span className="badge info">{data.total_vessels_affected} vessels affected</span>
        <span className="text-muted text-sm">{data.summary}</span>
      </div>

      {data.total_vessels_affected === 0 ? (
        <div className="card">
          <div className="state-box">
            <div className="state-icon">✅</div>
            <p>No vessels require alternative routing at this time.</p>
            <p className="text-sm">All vessel risk scores are below the routing threshold (50/100).</p>
          </div>
        </div>
      ) : (
        data.recommendations?.map(rec => (
          <RoutingCard key={rec.vessel_id} rec={rec} />
        ))
      )}
    </Layout>
  )
}
