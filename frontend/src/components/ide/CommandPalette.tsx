import { useEffect, useMemo, useState } from 'react'

export type Command = {
  id: string
  label: string
  run: () => void
}

export function CommandPalette({ commands, onClose }: { commands: Command[]; onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)

  const results = useMemo(
    () => commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase())),
    [commands, query],
  )

  useEffect(() => setSelected(0), [query])

  const choose = (command: Command) => {
    command.run()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[15vh]" onClick={onClose}>
      <div className="panel w-full max-w-lg p-2" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          className="w-full !border-0 !bg-transparent !text-base"
          placeholder="Type a command…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') setSelected((s) => Math.min(s + 1, results.length - 1))
            else if (e.key === 'ArrowUp') setSelected((s) => Math.max(s - 1, 0))
            else if (e.key === 'Enter' && results[selected]) choose(results[selected])
            else if (e.key === 'Escape') onClose()
          }}
        />
        <div className="mt-1 max-h-72 overflow-auto border-t border-slate-800 pt-1">
          {results.map((c, i) => (
            <div
              key={c.id}
              className={`cursor-pointer rounded px-2 py-1.5 text-sm ${i === selected ? 'bg-blue-900/40 text-blue-200' : 'text-slate-300'}`}
              onMouseEnter={() => setSelected(i)}
              onClick={() => choose(c)}
            >
              {c.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
