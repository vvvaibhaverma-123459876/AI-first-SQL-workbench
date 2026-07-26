import { useEffect, useState } from 'react'
import { useFileStore } from '../../store/useFileStore'
import type { FileSearchResult } from '../../types'

export function ContentSearch({ workspaceId, onClose }: { workspaceId: string; onClose: () => void }) {
  const { searchContent, openFile } = useFileStore()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<FileSearchResult[]>([])

  useEffect(() => {
    const handle = setTimeout(async () => {
      setResults(await searchContent(workspaceId, query))
    }, 200)
    return () => clearTimeout(handle)
  }, [query, workspaceId, searchContent])

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
          placeholder="Search file contents…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Escape' && onClose()}
        />
        <div className="mt-1 max-h-72 overflow-auto border-t border-slate-800 pt-1">
          {query.trim() === '' ? (
            <div className="muted px-2 py-3 text-xs">Type to search across every file in this workspace.</div>
          ) : results.length === 0 ? (
            <div className="muted px-2 py-3 text-xs">No matches.</div>
          ) : (
            results.map((r) => (
              <div key={r.file_id} className="cursor-pointer rounded px-2 py-1.5 hover:bg-slate-800/60" onClick={() => choose(r.file_id)}>
                <div className="text-sm text-slate-200">{r.name}</div>
                <div className="muted truncate font-mono text-xs">{r.snippet}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
