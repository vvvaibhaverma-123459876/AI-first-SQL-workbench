import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Trash2 } from 'lucide-react'
import api from '../../services/api'
import { useAuthStore } from '../../store/useAuthStore'
import { useDashboardStore } from '../../store/useDashboardStore'
import type { ConnectionQueryResult, DashboardItem } from '../../types'
import { ChartView } from './ChartView'

// Each tile fetches its own data independently (own loading/error state,
// own request) rather than sharing useConnectionStore's single query-result
// slot -- a dashboard renders several tiles at once, and one slow or failed
// connection must not block or clobber the others' results.
export function DashboardTile({
  workspaceId,
  dashboardId,
  item,
  isFirst,
  isLast,
}: {
  workspaceId: string
  dashboardId: string
  item: DashboardItem
  isFirst: boolean
  isLast: boolean
}) {
  const { deleteItem, moveItem } = useDashboardStore()
  const [result, setResult] = useState<ConnectionQueryResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    const token = useAuthStore.getState().token
    setLoading(true)
    setError(null)
    api
      .post(`/workspaces/${workspaceId}/connections/${item.connection_id}/query`, { sql: item.sql }, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((res) => setResult(res.data))
      .catch((err) => setError((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Query failed.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item.id, item.sql, item.connection_id])

  return (
    <div className="flex flex-col rounded-lg border border-slate-800 bg-slate-900/40 p-2" style={{ gridColumn: `span ${item.width}` }}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="truncate text-xs font-semibold text-slate-200">{item.title}</span>
        <div className="flex shrink-0 items-center gap-1">
          <button title="Move up" disabled={isFirst} className="!border-0 !bg-transparent !p-0.5 disabled:opacity-30" onClick={() => moveItem(workspaceId, dashboardId, item.id, 'up')}>
            <ChevronUp size={13} />
          </button>
          <button title="Move down" disabled={isLast} className="!border-0 !bg-transparent !p-0.5 disabled:opacity-30" onClick={() => moveItem(workspaceId, dashboardId, item.id, 'down')}>
            <ChevronDown size={13} />
          </button>
          <button title="Remove tile" className="!border-0 !bg-transparent !p-0.5 text-rose-400" onClick={() => deleteItem(workspaceId, dashboardId, item.id)}>
            <Trash2 size={13} />
          </button>
        </div>
      </div>
      <div className="min-h-[80px] flex-1 overflow-auto">
        {loading && <div className="muted p-2 text-xs">Loading…</div>}
        {!loading && error && <div className="rounded border border-rose-900/50 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-300">{error}</div>}
        {!loading && !error && result && <ChartView chartType={item.chart_type} columns={result.columns} rows={result.rows} xField={item.x_field} yFields={item.y_fields} />}
      </div>
    </div>
  )
}
