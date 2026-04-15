import { Lightbulb, Link2 } from 'lucide-react'
import { useStudioStore } from '../store/useStudioStore'

export function AIPanel() {
  const { aiExplanation, aiSuggestions, joinSuggestions, suggestTables } = useStudioStore()

  return (
    <div className="panel flex h-full flex-col gap-4 p-4">
      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Lightbulb size={16} /> AI Assistant</div>
        <button onClick={suggestTables}>Suggest Tables</button>
      </div>

      <div className="rounded-xl border border-slate-800 p-3">
        <div className="font-medium">SQL Explanation</div>
        <div className="muted mt-2 text-sm whitespace-pre-wrap">{aiExplanation || 'Run Explain to see a plain-English breakdown of the current query.'}</div>
      </div>

      <div className="rounded-xl border border-slate-800 p-3">
        <div className="font-medium">Relevant Tables</div>
        <div className="mt-2 space-y-3 text-sm">
          {aiSuggestions.map((item) => (
            <div key={item.table_name} className="rounded-lg border border-slate-800 p-2">
              <div className="font-semibold">{item.table_name}</div>
              <div className="muted mt-1">{item.reason}</div>
              <div className="mt-2 text-xs text-slate-300">{item.suggested_columns.join(', ')}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 p-3">
        <div className="mb-2 flex items-center gap-2 font-medium"><Link2 size={14} /> Suggested Joins</div>
        <div className="space-y-2 text-xs text-slate-300">
          {joinSuggestions.map((join, index) => <div key={index}>{join}</div>)}
        </div>
      </div>
    </div>
  )
}
