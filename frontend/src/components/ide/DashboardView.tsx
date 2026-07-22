import { useEffect, useState } from 'react'
import { Plus, Share2 } from 'lucide-react'
import { useConnectionStore } from '../../store/useConnectionStore'
import { useDashboardStore } from '../../store/useDashboardStore'
import type { ChartType } from '../../types'
import { DashboardTile } from './DashboardTile'
import { ShareDialog } from './ShareDialog'

const CHART_TYPES: ChartType[] = ['table', 'bar', 'line', 'pie', 'scatter']

export function DashboardView({ workspaceId, dashboardId }: { workspaceId: string; dashboardId: string }) {
  const { currentDashboard, loading, error, loadDashboard, addItem } = useDashboardStore()
  const { connections, loadConnections } = useConnectionStore()
  const [showAddForm, setShowAddForm] = useState(false)
  const [sharing, setSharing] = useState(false)
  const [title, setTitle] = useState('')
  const [connectionId, setConnectionId] = useState('')
  const [sql, setSql] = useState('')
  const [chartType, setChartType] = useState<ChartType>('table')
  const [addError, setAddError] = useState<string | null>(null)

  useEffect(() => {
    loadDashboard(workspaceId, dashboardId)
    loadConnections(workspaceId)
  }, [workspaceId, dashboardId, loadDashboard, loadConnections])

  useEffect(() => {
    if (!connectionId && connections.length > 0) setConnectionId(connections[0].id)
  }, [connections, connectionId])

  const submitNewTile = async () => {
    if (!connectionId || !title.trim() || !sql.trim()) return
    setAddError(null)
    const created = await addItem(workspaceId, dashboardId, { connection_id: connectionId, title: title.trim(), sql, chart_type: chartType, width: 1 })
    if (!created) {
      setAddError(useDashboardStore.getState().error)
      return
    }
    setTitle('')
    setSql('')
    setChartType('table')
    setShowAddForm(false)
  }

  if (loading && !currentDashboard) return <div className="muted p-4 text-xs">Loading dashboard…</div>
  if (error && !currentDashboard) return <div className="p-4 text-xs text-rose-300">{error}</div>
  if (!currentDashboard) return null

  const sorted = [...currentDashboard.items].sort((a, b) => a.sort_order - b.sort_order)

  return (
    <div className="flex h-full flex-col overflow-auto p-3">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">{currentDashboard.name}</h2>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1 !py-1 !text-xs" onClick={() => setSharing(true)}>
            <Share2 size={13} />
            Share
          </button>
          <button className="flex items-center gap-1 !py-1 !text-xs" onClick={() => setShowAddForm((v) => !v)}>
            <Plus size={13} />
            Add chart
          </button>
        </div>
      </div>
      {sharing && <ShareDialog workspaceId={workspaceId} resourceType="dashboard" resourceId={dashboardId} resourceName={currentDashboard.name} onClose={() => setSharing(false)} />}

      {showAddForm && (
        <div className="mb-4 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
          <div className="mb-2 grid grid-cols-2 gap-2">
            <input className="!text-xs" placeholder="Tile title" value={title} onChange={(e) => setTitle(e.target.value)} />
            <select className="!text-xs" value={connectionId} onChange={(e) => setConnectionId(e.target.value)}>
              {connections.length === 0 && <option value="">No connections</option>}
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <textarea
            className="mb-2 w-full !text-xs"
            rows={3}
            placeholder="SELECT ... (read-only queries only)"
            value={sql}
            onChange={(e) => setSql(e.target.value)}
          />
          <div className="mb-2 flex items-center gap-2">
            <span className="muted text-[11px]">Chart type:</span>
            {CHART_TYPES.map((t) => (
              <button
                key={t}
                className={`!py-0.5 !text-[11px] ${chartType === t ? '!border-blue-700 !bg-blue-800' : ''}`}
                onClick={() => setChartType(t)}
                type="button"
              >
                {t}
              </button>
            ))}
          </div>
          {addError && <div className="mb-2 rounded border border-rose-900/50 bg-rose-950/30 px-2 py-1 text-[11px] text-rose-300">{addError}</div>}
          <div className="flex gap-2">
            <button className="!border-blue-800 !bg-blue-700 !py-1 !text-xs hover:!bg-blue-600" onClick={submitNewTile} disabled={!connectionId || !title.trim() || !sql.trim()}>
              Pin to dashboard
            </button>
            <button className="!py-1 !text-xs" onClick={() => setShowAddForm(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {sorted.length === 0 && !showAddForm && <div className="muted p-3 text-xs">No charts pinned yet. Click "Add chart" to pin your first query.</div>}

      <div className="grid grid-cols-3 gap-3">
        {sorted.map((item, i) => (
          <DashboardTile key={item.id} workspaceId={workspaceId} dashboardId={dashboardId} item={item} isFirst={i === 0} isLast={i === sorted.length - 1} />
        ))}
      </div>
    </div>
  )
}
