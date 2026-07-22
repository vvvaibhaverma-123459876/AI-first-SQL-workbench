import Editor from '@monaco-editor/react'
import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useSharingStore } from '../../store/useSharingStore'
import api from '../../services/api'
import { useAuthStore } from '../../store/useAuthStore'
import type { ChartType, SharedDashboardItem } from '../../types'
import { ChartView } from '../ide/ChartView'

function languageFor(name: string): string {
  if (name.endsWith('.sql')) return 'sql'
  if (name.endsWith('.md')) return 'markdown'
  if (name.endsWith('.json')) return 'json'
  return 'plaintext'
}

function SharedDashboardTile({ dashboardId, item }: { dashboardId: string; item: SharedDashboardItem }) {
  const [result, setResult] = useState<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = useAuthStore.getState().token
    setLoading(true)
    setError(null)
    api
      .post(`/shared/dashboards/${dashboardId}/items/${item.id}/run`, {}, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((res) => setResult(res.data))
      .catch((err) => setError((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Query failed.'))
      .finally(() => setLoading(false))
  }, [dashboardId, item.id])

  return (
    <div className="flex flex-col rounded-lg border border-slate-800 bg-slate-900/40 p-2" style={{ gridColumn: `span ${item.width}` }}>
      <div className="mb-1 truncate text-xs font-semibold text-slate-200">{item.title}</div>
      <div className="min-h-[80px] flex-1 overflow-auto">
        {loading && <div className="muted p-2 text-xs">Loading…</div>}
        {!loading && error && <div className="rounded border border-rose-900/50 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-300">{error}</div>}
        {!loading && !error && result && (
          <ChartView chartType={item.chart_type as ChartType} columns={result.columns} rows={result.rows} xField={item.x_field} yFields={item.y_fields} />
        )}
      </div>
    </div>
  )
}

export function SharedResourceView() {
  const { activeShare, activeFile, activeDashboard, error, closeShared, updateSharedFileContent } = useSharingStore()
  const [draft, setDraft] = useState('')

  useEffect(() => {
    if (activeFile) setDraft(activeFile.content)
  }, [activeFile])

  if (!activeShare) return null

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      <div className="flex items-center gap-3 border-b border-slate-800 px-5 py-3">
        <button className="flex items-center gap-1 !border-0 !bg-transparent !p-1 text-slate-400 hover:text-slate-200" onClick={closeShared}>
          <ArrowLeft size={15} />
          Back
        </button>
        <span className="text-sm font-semibold">{activeShare.resource_name}</span>
        <span className="muted text-xs uppercase tracking-wide">
          Shared {activeShare.role === 'editor' ? '(can edit)' : '(view only)'}
        </span>
      </div>

      <div className="min-h-0 flex-1 p-3">
        {error && <div className="m-2 rounded border border-rose-900/50 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">{error}</div>}

        {activeShare.resource_type === 'file' && activeFile && (
          <div className="panel h-full overflow-hidden">
            <Editor
              language={languageFor(activeFile.name)}
              theme="vs-dark"
              value={draft}
              onChange={(value) => setDraft(value ?? '')}
              options={{ fontSize: 13, minimap: { enabled: false }, automaticLayout: true, readOnly: activeFile.role !== 'editor' }}
            />
            {activeFile.role === 'editor' && (
              <div className="flex justify-end border-t border-slate-800 px-3 py-2">
                <button
                  className="!border-blue-800 !bg-blue-700 !py-1 !text-xs hover:!bg-blue-600"
                  onClick={() => updateSharedFileContent(draft)}
                  disabled={draft === activeFile.content}
                >
                  Save
                </button>
              </div>
            )}
          </div>
        )}

        {activeShare.resource_type === 'dashboard' && activeDashboard && (
          <div className="grid grid-cols-3 gap-3 overflow-auto">
            {activeDashboard.items.length === 0 && <div className="muted p-3 text-xs">This dashboard has no charts pinned.</div>}
            {activeDashboard.items
              .slice()
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((item) => (
                <SharedDashboardTile key={item.id} dashboardId={activeDashboard.id} item={item} />
              ))}
          </div>
        )}
      </div>
    </div>
  )
}
