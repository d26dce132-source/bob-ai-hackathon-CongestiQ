import React, { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { Badge, ScoreBar, Loading, ErrorState, formatEta } from '../components/Shared'
import {
  fetchHealth, fetchVessels, fetchBerths, fetchCranes,
  fetchCongestion, fetchHotspots, fetchVesselRisks, fetchOperationsPlan,
} from '../api/client'

function StatCard({ icon, label, value, sub, variant }) {
  return (
    <div className={`stat-card ${variant || ''}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value ?? '—'}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

function levelVariant(level) {
  if (!level) return ''
  return { CRITICAL: 'critical', HIGH: 'high', MEDIUM: 'medium', LOW: 'success' }[level] || ''
}

export default function Overview() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([
      fetchHealth(),
      fetchVessels(),
      fetchBerths(),
      fetchCranes(),
      fetchCongestion(),
      fetchHotspots(),
      fetchVesselRisks(),
      fetchOperationsPlan(),
    ])
      .then(([health, vessels, berths, cranes, congestion, hotspots, risks, plan]) => {
        setData({
          health:     health.data,
          vessels:    vessels.data,
          berths:     berths.data,
          cranes:     cranes.data,
          congestion: congestion.data,
          hotspots:   hotspots.data,
          risks:      risks.data,
          plan:       plan.data,
        })
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }

  useEffect(load, [])

  if (loading) return <Layout title="Overview"><Loading /></Layout>
  if (error)   return <Layout title="Overview"><ErrorState message={error} onRetry={load} /></Layout>

  const { health, vessels, berths, cranes, congestion, hotspots, risks, plan } = data

  const availableBerths = berths.berths.filter(b => b.status === 'available').length
  const availableCranes = cranes.cranes.filter(c => c.status === 'available').length
  const criticalVessels = risks.vessels.filter(v => v.risk_level === 'CRITICAL').length
  const highVessels     = risks.vessels.filter(v => v.risk_level === 'HIGH').length
  const criticalHotspots = hotspots.hotspots.filter(h => h.severity === 'CRITICAL').length

  return (
    <Layout
      title="Port Operations Overview"
      subtitle={`Simulated data · Updated ${new Date().toLocaleTimeString()}`}
    >
      {/* Stat row */}
      <div className="stat-grid">
        <StatCard icon="🚢" label="Total Vessels" value={vessels.total}
          sub={`${risks.vessels.filter(v=>v.current_status==='berthed').length} berthed`}
          variant="accent" />
        <StatCard icon="⚠️" label="High/Critical Risk"
          value={criticalVessels + highVessels}
          sub={`${criticalVessels} critical · ${highVessels} high`}
          variant={criticalVessels > 0 ? 'critical' : highVessels > 0 ? 'high' : 'success'} />
        <StatCard icon="⚡" label="Congestion Level"
          value={congestion.overall_level}
          sub={`Score ${congestion.overall_score}/100`}
          variant={levelVariant(congestion.overall_level)} />
        <StatCard icon="🔥" label="Active Hotspots"
          value={hotspots.total_hotspots}
          sub={`${criticalHotspots} critical`}
          variant={criticalHotspots > 0 ? 'critical' : hotspots.total_hotspots > 0 ? 'high' : 'success'} />
        <StatCard icon="🏗️" label="Available Berths"
          value={availableBerths}
          sub={`of ${berths.total} total`}
          variant={availableBerths < 3 ? 'high' : 'success'} />
        <StatCard icon="🔧" label="Available Cranes"
          value={availableCranes}
          sub={`of ${cranes.total} total`}
          variant={availableCranes < 4 ? 'high' : 'success'} />
      </div>

      <div className="grid-2 mb-6">
        {/* Congestion summary */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">⚡ Congestion Summary</div>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
              <div className="gauge-wrap" style={{ padding: 0, minWidth: 120 }}>
                <div className={`gauge-circle ${congestion.overall_level}`}>
                  <span className="gauge-score">{congestion.overall_score?.toFixed(0)}</span>
                  <span className="gauge-label">{congestion.overall_level}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
                  Overall Score
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 13, marginBottom: 10, color: 'var(--text-muted)' }}>
                  {congestion.summary}
                </p>
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
                      {f.contribution?.toFixed(1)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Operations plan summary */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">📋 72-Hour Plan Summary</div>
            <span className="badge info">{plan.total_items} items</span>
          </div>
          <div className="card-body">
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
              {plan.executive_summary}
            </p>
            <div className="flex-row mb-4">
              <span className="badge CRITICAL">{plan.critical_items} Critical</span>
              <span className="badge HIGH">{plan.high_items} High</span>
              <span className="badge muted">{plan.total_items - plan.critical_items - plan.high_items} Other</span>
            </div>
            {plan.items?.slice(0, 4).map(item => (
              <div key={item.item_id} className="plan-item" style={{ padding: '10px 0', gridTemplateColumns: '6px 1fr auto' }}>
                <div className={`plan-stripe ${item.priority_level}`} style={{ minHeight: 30 }} />
                <div>
                  <div className="plan-issue" style={{ fontSize: 12 }}>{item.issue.slice(0, 90)}{item.issue.length > 90 ? '…' : ''}</div>
                  <div className="plan-action">{item.area}</div>
                </div>
                <Badge level={item.priority_level} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top risk vessels */}
      <div className="card mb-6">
        <div className="card-header">
          <div className="card-title">🚢 Highest Risk Vessels</div>
          <span className="text-sm text-muted">Top 6 · sorted by risk score</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Vessel</th>
                <th>Type</th>
                <th>Status</th>
                <th>ETA</th>
                <th>Berth</th>
                <th>Risk Score</th>
                <th>Risk Level</th>
              </tr>
            </thead>
            <tbody>
              {risks.vessels?.slice(0, 6).map(v => (
                <tr key={v.vessel_id}>
                  <td style={{ fontWeight: 500 }}>{v.vessel_name}</td>
                  <td className="td-muted">{v.vessel_type?.replace('_', ' ')}</td>
                  <td><span className="badge muted">{v.current_status}</span></td>
                  <td className="td-muted">{formatEta(v.eta)}</td>
                  <td className="td-mono">{v.berth_code || '—'}</td>
                  <td style={{ width: 160 }}>
                    <ScoreBar score={v.risk_score} level={v.risk_level} />
                  </td>
                  <td><Badge level={v.risk_level} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  )
}
