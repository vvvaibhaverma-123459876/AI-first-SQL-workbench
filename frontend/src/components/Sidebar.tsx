import { Database, History, Save } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useStudioStore } from '../store/useStudioStore'

export function Sidebar() {
  const { schema, history, savedQueries, openSQLInTab, deleteSavedQuery } = useStudioStore()
  const [search, setSearch] = useState('')

  const filteredTables = useMemo(() => {
    const tables = schema?.tables ?? []
    return tables.filter((table) => table.name.toLowerCase().includes(search.toLowerCase()))
  }, [schema, search])

  return (
    <div className="panel flex h-full flex-col gap-4 p-4">
      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Database size={16} /> Schema</div>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search tables" className="w-full" />
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-auto">
        {filteredTables.map((table) => (
          <div key={table.name} className="rounded-xl border border-slate-800 p-3">
            <div className="font-medium text-slate-100">{table.name}</div>
            <div className="mt-2 space-y-1 text-xs text-slate-400">
              {table.columns.slice(0, 8).map((column) => (
                <div key={column.name}>{column.name} · {column.data_type}</div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Save size={16} /> Saved Queries</div>
        <div className="max-h-40 space-y-2 overflow-auto">
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
        <div className="max-h-44 space-y-2 overflow-auto text-xs">
          {history.slice(0, 10).map((item) => (
            <div key={item.id} className="rounded-xl border border-slate-800 p-2">
              <div className="truncate text-slate-200">{item.sql_text}</div>
              <div className="muted mt-1">{item.status} · {item.execution_ms} ms</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
