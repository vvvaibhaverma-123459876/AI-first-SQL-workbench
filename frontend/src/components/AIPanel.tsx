import { Brain, Check, Cpu, Lightbulb, Link2, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useStudioStore } from '../store/useStudioStore'

export function AIPanel() {
  const {
    aiExplanation,
    aiSuggestions,
    joinSuggestions,
    suggestTables,
    aiStatus,
    refreshAIStatus,
    assistantResponse,
    assistantMemory,
    sendAssistantFeedback,
  } = useStudioStore()

  const statusTone = aiStatus?.status === 'connected' ? 'text-emerald-300' : aiStatus?.status === 'mock' ? 'text-amber-300' : 'text-rose-300'

  return (
    <div className="panel flex h-full flex-col gap-4 overflow-auto p-4">
      <div className="rounded-xl border border-slate-800 p-3">
        <div className="mb-2 flex items-center justify-between gap-2 text-sm font-semibold">
          <span className="flex items-center gap-2"><Cpu size={16} /> Local AI Runtime</span>
          <button onClick={refreshAIStatus} className="px-2 py-1"><RefreshCw size={13} /></button>
        </div>
        <div className={`text-sm ${statusTone}`}>{aiStatus?.status ?? 'checking'} · {aiStatus?.provider ?? 'unknown'}</div>
        <div className="muted mt-1 text-xs">Model: {aiStatus?.active_model ?? 'not selected'}</div>
        <div className="muted mt-1 text-xs">{aiStatus?.message ?? 'Checking local AI runtime...'}</div>
        <div className="mt-2 rounded-lg border border-emerald-900 bg-emerald-950/40 p-2 text-xs text-emerald-300">Local-only mode: no provider API key required.</div>
      </div>

      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><Lightbulb size={16} /> AI Assistant</div>
        <button onClick={suggestTables}>Suggest Tables</button>
      </div>

      {assistantResponse && (
        <div className="rounded-xl border border-slate-800 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2 font-medium"><Brain size={14} /> Assistant Run</div>
            <div className="text-xs text-slate-400">{Math.round((assistantResponse.confidence ?? 0) * 100)}% confidence</div>
          </div>
          <div className="space-y-2 text-xs">
            {assistantResponse.steps.map((step, index) => (
              <div key={`${step.name}-${index}`} className="rounded-lg border border-slate-800 p-2">
                <div className="flex items-center gap-2 text-slate-200"><Check size={12} /> {step.name} · {step.status}</div>
                <div className="muted mt-1">{step.detail}</div>
              </div>
            ))}
          </div>
          {assistantResponse.memory_id && (
            <div className="mt-3 flex gap-2">
              <button onClick={() => sendAssistantFeedback(true)}><ThumbsUp size={13} className="mr-1 inline" />Useful</button>
              <button onClick={() => sendAssistantFeedback(false)}><ThumbsDown size={13} className="mr-1 inline" />Not useful</button>
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-800 p-3">
        <div className="font-medium">SQL / Result Explanation</div>
        <div className="muted mt-2 whitespace-pre-wrap text-sm">{aiExplanation || 'Run Explain or Ask + Run to see a local explanation.'}</div>
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

      <div className="rounded-xl border border-slate-800 p-3">
        <div className="font-medium">Local Learning Memory</div>
        <div className="muted mt-1 text-xs">Recent successful assistant runs reused before calling Ollama.</div>
        <div className="mt-2 max-h-36 space-y-2 overflow-auto text-xs">
          {assistantMemory.slice(0, 6).map((item) => (
            <div key={item.id} className="rounded-lg border border-slate-800 p-2">
              <div className="truncate text-slate-200">{item.question}</div>
              <div className="muted mt-1">used {item.use_count}x · {Math.round(item.confidence * 100)}% · 👍 {item.positive_feedback} 👎 {item.negative_feedback}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
