import { useEffect, useState } from 'react'
import { Play } from 'lucide-react'
import { useConnectionStore } from '../../store/useConnectionStore'

export function QueryRunner({ workspaceId, sql }: { workspaceId: string; sql: string }) {
  const { connections, loadConnections, runQuery, queryResult, queryError, queryRunning } = useConnectionStore()
  const [connectionId, setConnectionId] = useState<string>('')

  useEffect(() => {
    loadConnections(workspaceId)
  }, [workspaceId, loadConnections])

  useEffect(() => {
    if (!connectionId && connections.length > 0) setConnectionId(connections[0].id)
  }, [connections, connectionId])

  const run = () => {
    if (!connectionId || !sql.trim()) return
    runQuery(workspaceId, connectionId, sql)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-slate-800 px-2 py-1.5">
        <select className="w-40 !py-1 !text-xs" value={connectionId} onChange={(e) => setConnectionId(e.target.value)}>
          {connections.length === 0 && <option value="">No connections</option>}
          {connections.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button
          className="flex items-center gap-1 !border-blue-800 !bg-blue-700 !py-1 !text-xs hover:!bg-blue-600"
          onClick={run}
          disabled={!connectionId || queryRunning}
          title="Run query"
        >
          <Play size={11} />
          {queryRunning ? 'Running…' : 'Run'}
        </button>
        {queryResult && (
          <span className="muted text-[11px]">
            {queryResult.row_count} row{queryResult.row_count === 1 ? '' : 's'}
            {queryResult.truncated ? ' (truncated)' : ''} in {queryResult.execution_ms}ms
          </span>
        )}
      </div>
      <div className="flex-1 overflow-auto">
        {queryError && <div className="m-2 rounded border border-rose-900/50 bg-rose-950/30 px-3 py-2 text-xs text-rose-300">{queryError}</div>}
        {queryResult && (
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-900">
              <tr>
                {queryResult.columns.map((col) => (
                  <th key={col} className="border-b border-slate-800 px-2 py-1 font-medium text-slate-400">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {queryResult.rows.map((row, i) => (
                <tr key={i} className="odd:bg-slate-900/40">
                  {queryResult.columns.map((col) => (
                    <td key={col} className="border-b border-slate-800/60 px-2 py-1 text-slate-300">
                      {String(row[col] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!queryError && !queryResult && <div className="muted p-3 text-xs">Pick a connection and press Run to execute this file against it.</div>}
      </div>
    </div>
  )
}
