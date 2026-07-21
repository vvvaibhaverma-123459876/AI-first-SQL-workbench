import { useEffect, useState } from 'react'
import { CheckCircle2, Database, Plus, Trash2, XCircle } from 'lucide-react'
import { useConnectionStore } from '../../store/useConnectionStore'
import type { ConnectorType } from '../../types'

type FieldSpec = { key: string; label: string; type?: 'text' | 'password' | 'number' | 'textarea'; optional?: boolean }

const FIELDS_BY_TYPE: Record<ConnectorType, FieldSpec[]> = {
  postgres: [
    { key: 'host', label: 'Host' },
    { key: 'port', label: 'Port', type: 'number' },
    { key: 'database', label: 'Database' },
    { key: 'username', label: 'Username' },
    { key: 'password', label: 'Password', type: 'password' },
  ],
  mysql: [
    { key: 'host', label: 'Host' },
    { key: 'port', label: 'Port', type: 'number' },
    { key: 'database', label: 'Database' },
    { key: 'username', label: 'Username' },
    { key: 'password', label: 'Password', type: 'password' },
  ],
  sqlite: [{ key: 'path', label: 'File path (on the server)' }],
  snowflake: [
    { key: 'account', label: 'Account' },
    { key: 'user', label: 'User' },
    { key: 'password', label: 'Password', type: 'password' },
    { key: 'warehouse', label: 'Warehouse' },
    { key: 'database', label: 'Database' },
    { key: 'schema', label: 'Schema' },
    { key: 'role', label: 'Role', optional: true },
  ],
  bigquery: [
    { key: 'project_id', label: 'Project ID' },
    { key: 'dataset', label: 'Dataset', optional: true },
    { key: 'service_account_json', label: 'Service account JSON key', type: 'textarea' },
  ],
  databricks: [
    { key: 'server_hostname', label: 'Server hostname' },
    { key: 'http_path', label: 'HTTP path' },
    { key: 'access_token', label: 'Access token', type: 'password' },
    { key: 'catalog', label: 'Catalog', optional: true },
    { key: 'schema', label: 'Schema', optional: true },
  ],
}

const CONNECTOR_LABELS: Record<ConnectorType, string> = {
  postgres: 'PostgreSQL',
  mysql: 'MySQL',
  sqlite: 'SQLite',
  snowflake: 'Snowflake',
  bigquery: 'BigQuery',
  databricks: 'Databricks',
}

function NewConnectionForm({ workspaceId, onDone }: { workspaceId: string; onDone: () => void }) {
  const { createConnection } = useConnectionStore()
  const [connectorType, setConnectorType] = useState<ConnectorType>('postgres')
  const [name, setName] = useState('')
  const [values, setValues] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const fields = FIELDS_BY_TYPE[connectorType]
      const config: Record<string, unknown> = {}
      for (const field of fields) {
        const raw = values[field.key] ?? ''
        if (!raw && field.optional) continue
        config[field.key] = field.type === 'number' ? Number(raw) : raw
      }
      await createConnection(workspaceId, name, connectorType, config)
      onDone()
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Could not create connection.'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2 border-t border-slate-800 p-3">
      <input className="w-full" placeholder="Connection name" value={name} onChange={(e) => setName(e.target.value)} required />
      <select
        className="w-full"
        value={connectorType}
        onChange={(e) => {
          setConnectorType(e.target.value as ConnectorType)
          setValues({})
        }}
      >
        {(Object.keys(CONNECTOR_LABELS) as ConnectorType[]).map((t) => (
          <option key={t} value={t}>
            {CONNECTOR_LABELS[t]}
          </option>
        ))}
      </select>
      {FIELDS_BY_TYPE[connectorType].map((field) =>
        field.type === 'textarea' ? (
          <textarea
            key={field.key}
            className="w-full"
            placeholder={field.label}
            rows={3}
            value={values[field.key] ?? ''}
            onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
            required={!field.optional}
          />
        ) : (
          <input
            key={field.key}
            type={field.type === 'password' ? 'password' : field.type === 'number' ? 'number' : 'text'}
            className="w-full"
            placeholder={field.label}
            value={values[field.key] ?? ''}
            onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
            required={!field.optional}
          />
        ),
      )}
      {error && <div className="rounded border border-rose-900/50 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-300">{error}</div>}
      <div className="flex gap-2">
        <button type="submit" disabled={submitting} className="flex-1 !border-blue-800 !bg-blue-700 hover:!bg-blue-600">
          {submitting ? 'Creating…' : 'Create'}
        </button>
        <button type="button" className="flex-1" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  )
}

export function ConnectionsPanel({ workspaceId }: { workspaceId: string }) {
  const { connections, loadConnections, deleteConnection, testConnection } = useConnectionStore()
  const [creating, setCreating] = useState(false)
  const [testing, setTesting] = useState<string | null>(null)

  useEffect(() => {
    loadConnections(workspaceId)
  }, [workspaceId, loadConnections])

  const handleTest = async (connectionId: string) => {
    setTesting(connectionId)
    try {
      await testConnection(workspaceId, connectionId)
    } finally {
      setTesting(null)
    }
  }

  const handleDelete = async (connectionId: string, name: string) => {
    if (confirm(`Delete connection "${name}"?`)) await deleteConnection(workspaceId, connectionId)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-2 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Connections</span>
        <button className="!border-0 !bg-transparent !p-1" title="New connection" onClick={() => setCreating((c) => !c)}>
          <Plus size={13} />
        </button>
      </div>
      <div className="flex-1 overflow-auto">
        {connections.length === 0 && !creating ? (
          <div className="muted px-3 py-4 text-xs">No connections yet. Create one above.</div>
        ) : (
          connections.map((c) => (
            <div key={c.id} className="group flex items-center gap-1.5 rounded px-2 py-1.5 text-sm hover:bg-slate-800/60">
              <Database size={13} className="shrink-0 text-blue-400" />
              <span className="truncate text-slate-200">{c.name}</span>
              <span className="muted shrink-0 text-[10px] uppercase tracking-wide">{c.connector_type}</span>
              {c.last_test_ok === true && <CheckCircle2 size={12} className="shrink-0 text-emerald-500" />}
              {c.last_test_ok === false && <XCircle size={12} className="shrink-0 text-rose-500" />}
              <span className="ml-auto hidden shrink-0 items-center gap-1 group-hover:flex">
                <button className="!border-0 !bg-transparent !p-0.5 text-[10px]" onClick={() => handleTest(c.id)} disabled={testing === c.id}>
                  {testing === c.id ? '…' : 'Test'}
                </button>
                <button className="!border-0 !bg-transparent !p-0.5 hover:!text-rose-400" title="Delete" onClick={() => handleDelete(c.id, c.name)}>
                  <Trash2 size={12} />
                </button>
              </span>
            </div>
          ))
        )}
      </div>
      {creating && <NewConnectionForm workspaceId={workspaceId} onDone={() => setCreating(false)} />}
    </div>
  )
}
