import { flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { Download, Terminal } from 'lucide-react'
import { useMemo } from 'react'
import { useStudioStore } from '../store/useStudioStore'

function MiniBarChart({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  const numericCols = columns.filter((col) => rows.every((r) => r[col] !== null && !isNaN(Number(r[col]))))
  const labelCols = columns.filter((col) => !numericCols.includes(col))
  if (numericCols.length === 0 || rows.length < 2 || rows.length > 30) return null

  const valueCol = numericCols[0]
  const labelCol = labelCols[0] ?? columns[0]
  const values = rows.map((r) => Number(r[valueCol]))
  const max = Math.max(...values)
  if (max === 0) return null

  const fmt = (v: number) => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(1)}K` : String(v)

  return (
    <div className="mt-3 rounded-xl border border-slate-800 p-3">
      <div className="mb-2 text-xs font-semibold text-slate-300">{valueCol} by {labelCol}</div>
      <div className="space-y-1.5 overflow-hidden">
        {rows.slice(0, 15).map((row, i) => {
          const pct = (Number(row[valueCol]) / max) * 100
          return (
            <div key={i} className="flex items-center gap-2 text-xs">
              <div className="w-28 shrink-0 truncate text-right text-slate-400">{String(row[labelCol] ?? '')}</div>
              <div className="flex-1 overflow-hidden rounded-full bg-slate-800">
                <div className="h-4 rounded-full bg-gradient-to-r from-blue-600 to-blue-400 transition-all" style={{ width: `${pct}%` }} />
              </div>
              <div className="w-16 shrink-0 text-slate-300">{fmt(Number(row[valueCol]))}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function ResultsPanel() {
  const { results, logs, validationWarnings, validationErrors, exportCSV, assistantResponse, runAssistant, setAiPrompt } = useStudioStore()
  const columns = useMemo(() => (results?.columns ?? []).map((col) => ({ accessorKey: col, header: col })), [results])
  const table = useReactTable({ data: results?.rows ?? [], columns, getCoreRowModel: getCoreRowModel() })

  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold">Results</div>
          <div className="muted text-xs">
            {results
              ? <span>{results.row_count} rows · {results.cached ? <span className="text-emerald-400">cache hit</span> : `${results.execution_ms} ms`}</span>
              : 'No query executed yet'}
          </div>
        </div>
        {results && <button className="text-xs" onClick={exportCSV}><Download size={13} className="mr-1 inline" />Export CSV</button>}
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-slate-800">
        {results ? (
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-slate-800/90 text-left backdrop-blur">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th key={header.id} className="border-b border-slate-700 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row, i) => (
                <tr key={row.id} className={`border-b border-slate-900/60 ${i % 2 === 0 ? '' : 'bg-slate-800/20'}`}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2 text-slate-200">{String(cell.getValue() ?? 'NULL')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
            <div className="text-3xl">⚡</div>
            <div className="text-sm font-medium text-slate-300">Run a query to see results</div>
            <div className="text-xs text-slate-500">Type a question above and click <strong>Ask + Run</strong>, or write SQL and press <strong>⌘↵</strong></div>
          </div>
        )}
      </div>

      {results && <MiniBarChart columns={results.columns} rows={results.rows} />}

      {assistantResponse?.next_questions?.length ? (
        <div className="mt-3 rounded-xl border border-slate-800 p-3">
          <div className="mb-2 text-xs font-semibold text-slate-300">Follow-up analyses</div>
          <div className="flex flex-wrap gap-2">
            {assistantResponse.next_questions.map((q, i) => (
              <button key={i} className="text-xs text-slate-400 hover:text-slate-200" onClick={() => { setAiPrompt(q); runAssistant() }}>
                {q}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-3 grid grid-cols-3 gap-3">
        {validationWarnings.length > 0 && (
          <div className="rounded-xl border border-amber-900/50 bg-amber-950/20 p-3 text-xs">
            <div className="mb-1 font-semibold text-amber-400">Warnings</div>
            <div className="space-y-1 text-amber-300">{validationWarnings.map((w, i) => <div key={i}>{w}</div>)}</div>
          </div>
        )}
        {validationErrors.length > 0 && (
          <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-3 text-xs">
            <div className="mb-1 font-semibold text-rose-400">Errors</div>
            <div className="space-y-1 text-rose-300">{validationErrors.map((e, i) => <div key={i}>{e}</div>)}</div>
          </div>
        )}
        <div className="col-span-3 rounded-xl border border-slate-800 p-3 text-xs">
          <div className="mb-1 flex items-center gap-2 font-semibold text-slate-400"><Terminal size={12} /> Logs</div>
          <div className="max-h-16 space-y-0.5 overflow-auto text-slate-500">
            {logs.length > 0 ? logs.map((l, i) => <div key={i}>{l}</div>) : <span>No activity yet.</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
