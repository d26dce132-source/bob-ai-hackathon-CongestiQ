import React, { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { Badge, ScoreBar, Loading, ErrorState, formatEta } from '../components/Shared'
import { fetchVesselRisks } from '../api/client'

const LEVELS = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export default function Vessels() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [filter, setFilter] = useState('ALL')
  const [expanded, setExpanded] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchVesselRisks()
      .then(r => { setData(r.data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }
  useEffect(load, [])

  if (loading) return <Layout title="Vessels"><Loading /></Layout>
  if (error)   return <Layout title="Vessels"><ErrorState message={error} onRetry={load} /></Layout>

  const vessels = filter === 'ALL'
    ? data.vessels
    : data.vessels.filter(v => v.risk_level === filter)

  const counts = LEVELS.reduce((acc, l) => {
    acc[l] = l === 'ALL' ? data.total : data.vessels.filter(v => v.risk_level === l).length
    return acc
  }, {})

  return (
    <Layout
      title="Vessel Risk Table"
      subtitle={`${data.total} vessel(s) · sorted by risk score`}
    >
      {/* Filter pills */}
      <div className="flex-row mb-4" style={{ flexWrap: 'wrap' }}>
        {LEVELS.map(l => (
          <button
            key={l}
            onClick={() => setFilter(l)}
            style={{
              padding: '5px 14px',
              borderRadius: 20,
              border: '1px solid var(--border)',
              background: filter === l ? 'var(--accent)' : 'var(--surface)',
              color: filter === l ? 'white' : 'var(--text)',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {l} ({counts[l]})
          </button>
        ))}
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 28 }}></th>
                <th>Vessel</th>
                <th>Type</th>
                <th>Status</th>
                <th>ETA</th>
                <th>Berth</th>
                <th>Delay</th>
                <th>Risk Score</th>
                <th>Risk Level</th>
              </tr>
            </thead>
            <tbody>
              {vessels.map(v => (
                <React.Fragment key={v.vessel_id}>
                  <tr
                    style={{ cursor: 'pointer' }}
                    onClick={() => setExpanded(expanded === v.vessel_id ? null : v.vessel_id)}
                  >
                    <td style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                      {expanded === v.vessel_id ? '▾' : '▸'}
                    </td>
                    <td style={{ fontWeight: 500 }}>{v.vessel_name}</td>
                    <td className="td-muted">{v.vessel_type?.replace('_', ' ')}</td>
                    <td><span className="badge muted">{v.current_status}</span></td>
                    <td className="td-muted">{formatEta(v.eta)}</td>
                    <td className="td-mono">{v.berth_code || '—'}</td>
                    <td className="td-muted">
                      {v.delay_hours > 0 ? `+${v.delay_hours}h` : '—'}
                    </td>
                    <td style={{ width: 140 }}>
                      <ScoreBar score={v.risk_score} level={v.risk_level} />
                    </td>
                    <td><Badge level={v.risk_level} /></td>
                  </tr>
                  {expanded === v.vessel_id && (
                    <tr>
                      <td colSpan={9} style={{ background: 'var(--surface2)', padding: '12px 20px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                          <div>
                            <div className="section-heading" style={{ fontSize: 13, marginBottom: 8 }}>
                              Risk Factors
                            </div>
                            {v.factors?.map(f => (
                              <div key={f.name} className="factor-row">
                                <div className="factor-name">{f.name}</div>
                                <div>
                                  <ScoreBar score={f.contribution * 4} level={v.risk_level} />
                                  <div className="factor-desc">{f.description}</div>
                                </div>
                                <div style={{ textAlign: 'right', fontSize: 12, fontWeight: 600 }}>
                                  {f.contribution?.toFixed(1)}
                                </div>
                              </div>
                            ))}
                          </div>
                          <div>
                            <div className="section-heading" style={{ fontSize: 13, marginBottom: 8 }}>
                              Recommendation
                            </div>
                            <p style={{ fontSize: 13, color: 'var(--text)' }}>{v.recommendation}</p>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
        {vessels.length === 0 && (
          <div className="state-box">
            <div className="state-icon">✅</div>
            <p>No vessels at {filter} risk level</p>
          </div>
        )}
      </div>
    </Layout>
  )
}
