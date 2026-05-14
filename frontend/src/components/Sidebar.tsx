import { Database, Eye, History, Save } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useStudioStore } from '../store/useStudioStore'

export function Sidebar() {
  const { schema, history, savedQueries, openSQLInTab, deleteSavedQuery, previewTable, tablePreview, insertSQL } = useStudioStore()
  const [search, setSearch] = useState('')

  const filteredTables = useMemo(() => {
    const tables = schema?.tables ?? []
    const needle = search.toLowerCase()
    return tables.filter((table) => table.name.toLowerCase().includes(needle) || table.columns.some((column) => column.name.toLowerCase().includes(needle)))
  }, [schema, search])

  return (
    <div className="panel flex h-full flex-col gap-4 p-4">
      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Database size={16} /> Schema</div>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search tables or columns" className="w-full" />
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-auto">
        {filteredTables.map((table) => (
          <div key={table.name} className="rounded-xl border border-slate-800 p-3">
            <div className="flex items-center justify-between gap-2">
              <button className="px-2 py-1 text-left font-medium text-slate-100" onClick={() => insertSQL(`SELECT * FROM ${table.name} LIMIT 20;`)}>{table.name}</button>
              <button className="px-2 py-1" title="Preview table" onClick={() => previewTable(table.name)}><Eye size={13} /></button>
            </div>
            <div className="mt-2 space-y-1 text-xs text-slate-400">
              {table.columns.slice(0, 10).map((column) => (
                <button key={column.name} onClick={() => insertSQL(column.name)} className="mr-1 mt-1 px-2 py-1 text-xs">
                  {column.name} · {column.data_type}{column.is_primary_key ? ' · PK' : ''}{column.is_foreign_key ? ' · FK' : ''}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {tablePreview && (
        <div className="rounded-xl border border-slate-800 p-3 text-xs">
          <div className="font-semibold text-slate-200">Preview: {tablePreview.table_name}</div>
          <div className="muted mt-1">{tablePreview.rows.length} sample rows</div>
          <div className="mt-2 max-h-28 overflow-auto rounded-lg border border-slate-800 p-2">
            {tablePreview.rows.slice(0, 3).map((row, index) => (
              <pre key={index} className="mb-2 whitespace-pre-wrap text-[10px] text-slate-300">{JSON.stringify(row, null, 2)}</pre>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Save size={16} /> Saved Queries</div>
        <div className="max-h-36 space-y-2 overflow-auto">
          {savedQueries.map((item) => (
            <div key={item.id} className="rounded-xl border border-slate-800 p-2 text-sm">
              <div className="font-medium">{item.name}</div>
              <div className="mt-2 flex gap-2">
                <button onClick={() => openSQLInTab(item.name, item.sql_text)}>Open</button>
                <button onClick={() => deleteSavedQuery(item.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><History size={16} /> History</div>
        <div className="max-h-36 space-y-2 overflow-auto text-xs">
          {history.slice(0, 10).map((item) => (
            <button key={item.id} onClick={() => openSQLInTab(`History ${item.id}`, item.sql_text)} className="block w-full rounded-xl border border-slate-800 p-2 text-left">
              <div className="truncate text-slate-200">{item.sql_text}</div>
              <div className="muted mt-1">{item.status} · {item.execution_ms} ms</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
