import { useEffect, useMemo, useState } from 'react'
import { useFileStore } from '../../store/useFileStore'

function fuzzyMatch(name: string, query: string): boolean {
  if (!query) return true
  let qi = 0
  const lowerName = name.toLowerCase()
  const lowerQuery = query.toLowerCase()
  for (let i = 0; i < lowerName.length && qi < lowerQuery.length; i++) {
    if (lowerName[i] === lowerQuery[qi]) qi++
  }
  return qi === lowerQuery.length
}

export function QuickOpen({ workspaceId, onClose }: { workspaceId: string; onClose: () => void }) {
  const { files, openFile } = useFileStore()
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)

  const results = useMemo(
    () => files.filter((f) => !f.is_folder && fuzzyMatch(f.name, query)).slice(0, 20),
    [files, query],
  )

  useEffect(() => setSelected(0), [query])

  const choose = (fileId: string) => {
    openFile(workspaceId, fileId)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[15vh]" onClick={onClose}>
      <div className="panel w-full max-w-lg p-2" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          className="w-full !border-0 !bg-transparent !text-base"
          placeholder="Go to file by name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') setSelected((s) => Math.min(s + 1, results.length - 1))
            else if (e.key === 'ArrowUp') setSelected((s) => Math.max(s - 1, 0))
            else if (e.key === 'Enter' && results[selected]) choose(results[selected].id)
            else if (e.key === 'Escape') onClose()
          }}
        />
        <div className="mt-1 max-h-72 overflow-auto border-t border-slate-800 pt-1">
          {results.length === 0 ? (
            <div className="muted px-2 py-3 text-xs">No matching files.</div>
          ) : (
            results.map((f, i) => (
              <div
                key={f.id}
                className={`cursor-pointer rounded px-2 py-1.5 text-sm ${i === selected ? 'bg-blue-900/40 text-blue-200' : 'text-slate-300'}`}
                onMouseEnter={() => setSelected(i)}
                onClick={() => choose(f.id)}
              >
                {f.name}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
