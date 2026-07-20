import { ChevronDown, ChevronRight, Database, Eye, History, Save, Search, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useStudioStore } from '../store/useStudioStore'

export function Sidebar() {
  const { schema, history, savedQueries, openSQLInTab, deleteSavedQuery, previewTable, tablePreview, insertSQL } = useStudioStore()
  const [search, setSearch] = useState('')
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set())

  const filteredTables = useMemo(() => {
    const tables = schema?.tables ?? []
    const needle = search.toLowerCase()
    if (!needle) return tables
    return tables.filter((t) => t.name.toLowerCase().includes(needle) || t.columns.some((c) => c.name.toLowerCase().includes(needle)))
  }, [schema, search])

  const toggleTable = (name: string) =>
    setExpandedTables((prev) => { const s = new Set(prev); s.has(name) ? s.delete(name) : s.add(name); return s })

  return (
    <div className="panel flex h-full flex-col gap-3 p-4">
      {/* Schema search */}
      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200">
          <Database size={15} /> Schema
          <span className="ml-auto text-xs font-normal text-slate-500">{schema?.tables.length ?? 0} tables</span>
        </div>
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search tables or columns…" className="w-full pl-7 text-xs" />
        </div>
      </div>

      {/* Tables list */}
      <div className="min-h-0 flex-1 space-y-1.5 overflow-auto">
        {filteredTables.map((table) => {
          const expanded = expandedTables.has(table.name)
          return (
            <div key={table.name} className="rounded-xl border border-slate-800 bg-slate-800/30">
              <div className="flex items-center gap-1 px-2 py-2">
                <button className="border-0 bg-transparent p-0 text-slate-500" onClick={() => toggleTable(table.name)}>
                  {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                </button>
                <button
                  className="flex-1 border-0 bg-transparent px-1 py-0 text-left text-sm font-medium text-slate-100 hover:text-blue-300"
                  onClick={() => insertSQL(`SELECT * FROM ${table.name} LIMIT 20;`)}
                >
                  {table.name}
                </button>
                <button
                  className="border-0 bg-transparent p-1 text-slate-600 hover:text-slate-300"
                  title="Preview table"
                  onClick={() => previewTable(table.name)}
                >
                  <Eye size={13} />
                </button>
              </div>

              {expanded && (
                <div className="border-t border-slate-800 px-3 pb-2 pt-1.5">
                  <div className="flex flex-wrap gap-1">
                    {table.columns.map((col) => (
                      <button
                        key={col.name}
                        onClick={() => insertSQL(col.name)}
                        className="border-slate-700/50 bg-slate-800/60 px-1.5 py-0.5 text-[11px] text-slate-400 hover:text-slate-200"
                        title={col.data_type}
                      >
                        {col.is_primary_key ? '🔑 ' : col.is_foreign_key ? '🔗 ' : ''}{col.name}
                        <span className="ml-1 text-slate-600">{col.data_type.toLowerCase()}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Table preview */}
      {tablePreview && (
        <div className="rounded-xl border border-blue-900/50 bg-blue-950/20 p-3 text-xs">
          <div className="mb-1 font-semibold text-blue-300">Preview: {tablePreview.table_name}</div>
          <div className="max-h-32 overflow-auto rounded border border-slate-800">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="bg-slate-800">
                  {tablePreview.columns.slice(0, 5).map((c) => <th key={c} className="px-2 py-1 text-left text-slate-400">{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {tablePreview.rows.slice(0, 4).map((row, i) => (
                  <tr key={i} className="border-t border-slate-800">
                    {tablePreview.columns.slice(0, 5).map((c) => (
                      <td key={c} className="truncate px-2 py-1 text-slate-300" style={{ maxWidth: '80px' }}>{String(row[c] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Saved queries */}
      {savedQueries.length > 0 && (
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200"><Save size={14} /> Saved</div>
          <div className="max-h-32 space-y-1 overflow-auto">
            {savedQueries.map((item) => (
              <div key={item.id} className="flex items-center gap-2 rounded-lg border border-slate-800 px-2 py-1.5 text-xs">
                <button className="flex-1 border-0 bg-transparent p-0 text-left text-slate-300 hover:text-slate-100" onClick={() => openSQLInTab(item.name, item.sql_text)}>
                  {item.name}
                </button>
                <button className="border-0 bg-transparent p-0 text-slate-600 hover:text-rose-400" onClick={() => deleteSavedQuery(item.id)}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History */}
      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200"><History size={14} /> History</div>
        <div className="max-h-32 space-y-1 overflow-auto">
          {history.slice(0, 10).map((item) => (
            <button
              key={item.id}
              onClick={() => openSQLInTab(`History #${item.id}`, item.sql_text)}
              className="block w-full rounded-lg border border-slate-800 px-2 py-1.5 text-left text-xs hover:border-slate-700"
            >
              <div className="truncate text-slate-300">{item.sql_text}</div>
              <div className="mt-0.5 text-slate-500">
                <span className={item.status === 'success' ? 'text-emerald-500' : 'text-rose-500'}>{item.status}</span>
                {' · '}{item.execution_ms} ms
              </div>
            </button>
          ))}
          {history.length === 0 && <div className="text-xs text-slate-600">No queries run yet.</div>}
        </div>
      </div>
    </div>
  )
}
