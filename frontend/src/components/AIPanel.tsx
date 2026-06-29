import { Brain, Check, Cpu, Lightbulb, Link2, RefreshCw, ThumbsDown, ThumbsUp, Zap } from 'lucide-react'
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
    assistantLoading,
  } = useStudioStore()

  const statusColor =
    aiStatus?.status === 'connected' ? 'text-emerald-300' :
    aiStatus?.status === 'mock' ? 'text-amber-300' :
    'text-rose-300'

  const statusDot =
    aiStatus?.status === 'connected' ? 'bg-emerald-400' :
    aiStatus?.status === 'mock' ? 'bg-amber-400' :
    'bg-rose-400'

  return (
    <div className="panel flex h-full flex-col gap-3 overflow-auto p-4">
      {/* Runtime status */}
      <div className="rounded-xl border border-slate-800 bg-slate-800/30 p-3">
        <div className="mb-2 flex items-center justify-between gap-2 text-sm font-semibold text-slate-200">
          <span className="flex items-center gap-2"><Cpu size={15} /> Local AI Runtime</span>
          <button className="border-0 bg-transparent p-1 text-slate-500 hover:text-slate-300" onClick={refreshAIStatus}>
            <RefreshCw size={13} />
          </button>
        </div>
        <div className={`flex items-center gap-2 text-sm ${statusColor}`}>
          <span className={`inline-block h-2 w-2 rounded-full ${statusDot} ${aiStatus?.status === 'connected' ? 'animate-pulse' : ''}`} />
          {aiStatus?.status ?? 'checking'} · {aiStatus?.provider ?? 'unknown'}
        </div>
        <div className="muted mt-1 text-xs">Model: {aiStatus?.active_model ?? '—'}</div>
        <div className="muted mt-0.5 text-xs">{aiStatus?.message}</div>
        <div className="mt-2 rounded-lg border border-emerald-900/60 bg-emerald-950/30 px-2 py-1.5 text-xs text-emerald-400">
          🔒 Privacy-first · no data sent to cloud
        </div>
      </div>

      {/* Suggest tables */}
      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200"><Lightbulb size={15} /> Table Suggestions</div>
        <button className="w-full text-xs" onClick={suggestTables}>
          <Zap size={12} className="mr-1 inline" />Suggest Tables for Prompt
        </button>
      </div>

      {/* Assistant run steps */}
      {assistantLoading && (
        <div className="rounded-xl border border-blue-900/40 bg-blue-950/20 p-3">
          <div className="flex items-center gap-2 text-sm text-blue-300">
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-700 border-t-blue-300" />
            AI is working…
          </div>
        </div>
      )}

      {assistantResponse && !assistantLoading && (
        <div className="rounded-xl border border-slate-800 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
              <Brain size={14} /> Assistant
            </div>
            <div className="text-xs text-slate-400">{Math.round((assistantResponse.confidence ?? 0) * 100)}% confidence</div>
          </div>
          <div className="space-y-1.5">
            {assistantResponse.steps.map((step, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg border border-slate-800/60 px-2 py-1.5 text-xs">
                <Check size={11} className={`mt-0.5 shrink-0 ${step.status === 'success' ? 'text-emerald-400' : step.status === 'error' ? 'text-rose-400' : 'text-amber-400'}`} />
                <div>
                  <div className="text-slate-200">{step.name}</div>
                  <div className="text-slate-500">{step.detail}</div>
                </div>
              </div>
            ))}
          </div>
          {assistantResponse.memory_id && (
            <div className="mt-2 flex gap-2">
              <button className="flex-1 text-xs !border-emerald-900/50 !bg-emerald-950/30 !text-emerald-400" onClick={() => sendAssistantFeedback(true)}>
                <ThumbsUp size={11} className="mr-1 inline" />Useful
              </button>
              <button className="flex-1 text-xs !border-rose-900/50 !bg-rose-950/30 !text-rose-400" onClick={() => sendAssistantFeedback(false)}>
                <ThumbsDown size={11} className="mr-1 inline" />Not useful
              </button>
            </div>
          )}
        </div>
      )}

      {/* Explanation */}
      <div className="rounded-xl border border-slate-800 p-3">
        <div className="mb-1 text-sm font-medium text-slate-200">Explanation</div>
        <div className="muted whitespace-pre-wrap text-xs leading-relaxed">
          {aiExplanation || 'Click Explain or Ask + Run to get a natural-language explanation of the query and results.'}
        </div>
      </div>

      {/* Table suggestions */}
      {aiSuggestions.length > 0 && (
        <div className="rounded-xl border border-slate-800 p-3">
          <div className="mb-2 text-sm font-medium text-slate-200">Relevant Tables</div>
          <div className="space-y-2">
            {aiSuggestions.map((item) => (
              <div key={item.table_name} className="rounded-lg border border-slate-800 p-2">
                <div className="text-sm font-semibold text-slate-100">{item.table_name}</div>
                <div className="muted mt-0.5 text-xs">{item.reason}</div>
                <div className="mt-1 text-xs text-blue-400">{item.suggested_columns.join(', ')}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Joins */}
      {joinSuggestions.length > 0 && (
        <div className="rounded-xl border border-slate-800 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200"><Link2 size={13} /> Suggested Joins</div>
          <div className="space-y-1">
            {joinSuggestions.map((j, i) => (
              <div key={i} className="rounded bg-slate-800/60 px-2 py-1 font-mono text-[11px] text-slate-300">{j}</div>
            ))}
          </div>
        </div>
      )}

      {/* Learning memory */}
      {assistantMemory.length > 0 && (
        <div className="rounded-xl border border-slate-800 p-3">
          <div className="mb-1 text-sm font-medium text-slate-200">Learning Memory</div>
          <div className="muted mb-2 text-xs">Successful runs cached locally — reused before calling AI.</div>
          <div className="max-h-36 space-y-1.5 overflow-auto">
            {assistantMemory.slice(0, 6).map((item) => (
              <div key={item.id} className="rounded-lg border border-slate-800 p-2">
                <div className="truncate text-xs text-slate-200">{item.question}</div>
                <div className="muted mt-0.5 text-[11px]">used {item.use_count}× · {Math.round(item.confidence * 100)}% · 👍{item.positive_feedback} 👎{item.negative_feedback}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
