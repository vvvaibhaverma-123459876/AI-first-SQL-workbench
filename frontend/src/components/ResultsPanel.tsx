import { flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table'
import { Download, Terminal } from 'lucide-react'
import { useMemo } from 'react'
import { useStudioStore } from '../store/useStudioStore'

export function ResultsPanel() {
  const { results, logs, validationWarnings, validationErrors, exportCSV } = useStudioStore()
  const columns = useMemo(() => (results?.columns ?? []).map((col) => ({ accessorKey: col, header: col })), [results])
  const table = useReactTable({ data: results?.rows ?? [], columns, getCoreRowModel: getCoreRowModel() })

  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold">Results</div>
          <div className="muted text-xs">{results ? `${results.row_count} rows · ${results.execution_ms} ms` : 'No query executed yet'}</div>
        </div>
        <button onClick={exportCSV}><Download size={14} className="mr-1 inline" />Export CSV</button>
      </div>

      <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-slate-800">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-800/70 text-left">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="border-b border-slate-800 px-3 py-2">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-b border-slate-900/60">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2 text-slate-200">{String(cell.getValue() ?? 'NULL')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-800 p-3 text-xs">
          <div className="font-semibold text-slate-200">Warnings</div>
          <div className="mt-2 space-y-1 text-amber-300">{validationWarnings.map((item, i) => <div key={i}>{item}</div>)}</div>
        </div>
        <div className="rounded-xl border border-slate-800 p-3 text-xs">
          <div className="font-semibold text-slate-200">Errors</div>
          <div className="mt-2 space-y-1 text-rose-300">{validationErrors.map((item, i) => <div key={i}>{item}</div>)}</div>
        </div>
        <div className="rounded-xl border border-slate-800 p-3 text-xs">
          <div className="mb-2 flex items-center gap-2 font-semibold text-slate-200"><Terminal size={14} /> Logs</div>
          <div className="space-y-1 text-slate-300">{logs.map((item, i) => <div key={i}>{item}</div>)}</div>
        </div>
      </div>
    </div>
  )
}
