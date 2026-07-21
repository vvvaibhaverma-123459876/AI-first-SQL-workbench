import { useEffect, useState } from 'react'
import { LayoutDashboard, Plus, Trash2 } from 'lucide-react'
import { useDashboardStore } from '../../store/useDashboardStore'

export function DashboardsPanel({ workspaceId, onOpen }: { workspaceId: string; onOpen: (dashboardId: string) => void }) {
  const { dashboards, loadDashboards, createDashboard, deleteDashboard } = useDashboardStore()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadDashboards(workspaceId)
  }, [workspaceId, loadDashboards])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const created = await createDashboard(workspaceId, name)
      setName('')
      setCreating(false)
      onOpen(created.id)
    } catch (err) {
      setError((err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Could not create dashboard.')
    }
  }

  const handleDelete = async (id: string, dashboardName: string) => {
    if (confirm(`Delete dashboard "${dashboardName}"?`)) await deleteDashboard(workspaceId, id)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-2 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Dashboards</span>
        <button className="!border-0 !bg-transparent !p-1" title="New dashboard" onClick={() => setCreating((c) => !c)}>
          <Plus size={13} />
        </button>
      </div>
      <div className="flex-1 overflow-auto">
        {dashboards.length === 0 && !creating ? (
          <div className="muted px-3 py-4 text-xs">No dashboards yet. Create one above.</div>
        ) : (
          dashboards.map((d) => (
            <div key={d.id} className="group flex items-center gap-1.5 rounded px-2 py-1.5 text-sm hover:bg-slate-800/60">
              <button className="flex min-w-0 flex-1 items-center gap-1.5 !border-0 !bg-transparent !p-0 text-left" onClick={() => onOpen(d.id)}>
                <LayoutDashboard size={13} className="shrink-0 text-blue-400" />
                <span className="truncate text-slate-200">{d.name}</span>
              </button>
              <button className="ml-auto hidden !border-0 !bg-transparent !p-0.5 group-hover:block hover:!text-rose-400" title="Delete" onClick={() => handleDelete(d.id, d.name)}>
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}
      </div>
      {creating && (
        <form onSubmit={submit} className="space-y-2 border-t border-slate-800 p-3">
          <input className="w-full" placeholder="Dashboard name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
          {error && <div className="rounded border border-rose-900/50 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-300">{error}</div>}
          <div className="flex gap-2">
            <button type="submit" className="flex-1 !border-blue-800 !bg-blue-700 hover:!bg-blue-600">
              Create
            </button>
            <button type="button" className="flex-1" onClick={() => setCreating(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
