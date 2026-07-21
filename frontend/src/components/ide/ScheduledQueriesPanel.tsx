import { useEffect, useState } from 'react'
import { Clock, Play, Plus, Trash2 } from 'lucide-react'
import { useConnectionStore } from '../../store/useConnectionStore'
import { useScheduledQueryStore } from '../../store/useScheduledQueryStore'
import type { ScheduleCondition } from '../../types'

function NewScheduleForm({ workspaceId, onDone }: { workspaceId: string; onDone: () => void }) {
  const { connections, loadConnections } = useConnectionStore()
  const { createSchedule, error } = useScheduledQueryStore()
  const [name, setName] = useState('')
  const [connectionId, setConnectionId] = useState('')
  const [sql, setSql] = useState('')
  const [cron, setCron] = useState('0 * * * *')
  const [condition, setCondition] = useState<ScheduleCondition>('always')
  const [conditionValue, setConditionValue] = useState('')
  const [webhookUrl, setWebhookUrl] = useState('')
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadConnections(workspaceId)
  }, [workspaceId, loadConnections])

  useEffect(() => {
    if (!connectionId && connections.length > 0) setConnectionId(connections[0].id)
  }, [connections, connectionId])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    const ok = await createSchedule(workspaceId, {
      connection_id: connectionId,
      name,
      sql,
      cron_expression: cron,
      condition,
      condition_value: condition === 'always' ? null : Number(conditionValue),
      notify_webhook_url: webhookUrl.trim() || null,
      notify_email: email.trim() || null,
    })
    setSubmitting(false)
    if (ok) onDone()
  }

  return (
    <form onSubmit={submit} className="space-y-2 border-t border-slate-800 p-3">
      <input className="w-full" placeholder="Schedule name" value={name} onChange={(e) => setName(e.target.value)} required />
      <select className="w-full" value={connectionId} onChange={(e) => setConnectionId(e.target.value)}>
        {connections.length === 0 && <option value="">No connections</option>}
        {connections.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <textarea className="w-full" placeholder="SELECT ... (read-only queries only)" rows={3} value={sql} onChange={(e) => setSql(e.target.value)} required />
      <div>
        <input className="w-full" placeholder="Cron expression (e.g. 0 * * * *)" value={cron} onChange={(e) => setCron(e.target.value)} required />
        <div className="muted mt-1 text-[10px]">Standard 5-field cron: minute hour day month weekday. "0 * * * *" = every hour.</div>
      </div>
      <div className="flex items-center gap-2">
        <select className="!py-1 !text-xs" value={condition} onChange={(e) => setCondition(e.target.value as ScheduleCondition)}>
          <option value="always">Always notify</option>
          <option value="threshold">Row count above threshold</option>
          <option value="diff">Row count changed by</option>
        </select>
        {condition !== 'always' && (
          <input className="w-24 !py-1 !text-xs" type="number" placeholder="value" value={conditionValue} onChange={(e) => setConditionValue(e.target.value)} required />
        )}
      </div>
      <input className="w-full" placeholder="Webhook URL (optional)" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} />
      <input className="w-full" placeholder="Notify email (optional, needs SMTP configured)" value={email} onChange={(e) => setEmail(e.target.value)} />
      {error && <div className="rounded border border-rose-900/50 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-300">{error}</div>}
      <div className="flex gap-2">
        <button type="submit" disabled={submitting || !connectionId} className="flex-1 !border-blue-800 !bg-blue-700 hover:!bg-blue-600">
          {submitting ? 'Creating…' : 'Create'}
        </button>
        <button type="button" className="flex-1" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  )
}

export function ScheduledQueriesPanel({ workspaceId }: { workspaceId: string }) {
  const { schedules, loadSchedules, deleteSchedule, runNow } = useScheduledQueryStore()
  const [creating, setCreating] = useState(false)
  const [running, setRunning] = useState<string | null>(null)

  useEffect(() => {
    loadSchedules(workspaceId)
  }, [workspaceId, loadSchedules])

  const handleRun = async (id: string) => {
    setRunning(id)
    try {
      await runNow(workspaceId, id)
    } finally {
      setRunning(null)
    }
  }

  const handleDelete = async (id: string, name: string) => {
    if (confirm(`Delete scheduled query "${name}"?`)) await deleteSchedule(workspaceId, id)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-2 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Scheduled Queries</span>
        <button className="!border-0 !bg-transparent !p-1" title="New scheduled query" onClick={() => setCreating((c) => !c)}>
          <Plus size={13} />
        </button>
      </div>
      <div className="flex-1 overflow-auto">
        {schedules.length === 0 && !creating ? (
          <div className="muted px-3 py-4 text-xs">No scheduled queries yet. Create one above.</div>
        ) : (
          schedules.map((s) => (
            <div key={s.id} className="group rounded px-2 py-2 text-sm hover:bg-slate-800/60">
              <div className="flex items-center gap-1.5">
                <Clock size={13} className="shrink-0 text-blue-400" />
                <span className="truncate text-slate-200">{s.name}</span>
                <span className="muted shrink-0 text-[10px]">{s.cron_expression}</span>
                {!s.is_active && <span className="shrink-0 rounded bg-slate-700 px-1 text-[10px] text-slate-300">paused</span>}
                <span className="ml-auto hidden shrink-0 items-center gap-1 group-hover:flex">
                  <button className="!border-0 !bg-transparent !p-0.5" title="Run now" onClick={() => handleRun(s.id)} disabled={running === s.id}>
                    <Play size={12} />
                  </button>
                  <button className="!border-0 !bg-transparent !p-0.5 hover:!text-rose-400" title="Delete" onClick={() => handleDelete(s.id, s.name)}>
                    <Trash2 size={12} />
                  </button>
                </span>
              </div>
              {s.last_status && (
                <div className="muted mt-0.5 truncate pl-5 text-[11px]" title={s.last_status}>
                  {running === s.id ? 'Running…' : s.last_status}
                  {s.last_row_count !== null && ` (${s.last_row_count} rows)`}
                </div>
              )}
            </div>
          ))
        )}
      </div>
      {creating && <NewScheduleForm workspaceId={workspaceId} onDone={() => setCreating(false)} />}
    </div>
  )
}
