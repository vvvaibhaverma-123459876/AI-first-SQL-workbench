import { useState } from 'react'
import { FileText, Search } from 'lucide-react'
import { useAiJobsStore } from '../../store/useAiJobsStore'
import { useFileStore } from '../../store/useFileStore'

const STATUS_COLOR: Record<string, string> = {
  queued: 'text-amber-400',
  running: 'text-amber-400',
  done: 'text-emerald-400',
  failed: 'text-rose-400',
}

// The summary is written for the markdown report file, where **bold**
// renders properly -- but this preview box is plain text, so strip the
// markers rather than show literal asterisks to the user.
function plainText(markdown: string): string {
  return markdown.replace(/\*\*(.+?)\*\*/g, '$1')
}

export function InvestigatePanel({ workspaceId }: { workspaceId: string }) {
  const [question, setQuestion] = useState('')
  const { activeJob, investigating, error, startInvestigation } = useAiJobsStore()
  const { loadFiles, openFile } = useFileStore()

  const submit = () => {
    if (!question.trim() || investigating) return
    startInvestigation(workspaceId, question.trim())
  }

  const openReport = async () => {
    const fileId = activeJob?.result?.file_id as string | undefined
    if (!fileId) return
    await loadFiles(workspaceId)
    await openFile(workspaceId, fileId)
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-auto p-3">
      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200">
          <Search size={15} /> Investigate
        </div>
        <div className="muted mb-2 text-xs">
          Ask an open-ended question. Runs the primary query, an automatic follow-up, and writes a report file into this workspace.
        </div>
        <textarea
          className="w-full resize-none rounded-lg border border-slate-800 bg-slate-900/60 p-2 text-xs text-slate-200"
          rows={3}
          placeholder="e.g. why did signups drop last month?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={investigating}
        />
        <button
          className="mt-2 flex w-full items-center justify-center gap-1 !border-blue-800 !bg-blue-700 !py-1.5 !text-xs hover:!bg-blue-600"
          onClick={submit}
          disabled={!question.trim() || investigating}
        >
          {investigating ? 'Investigating…' : 'Run Investigation'}
        </button>
      </div>

      {error && <div className="rounded-lg border border-rose-900/50 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-300">{error}</div>}

      {activeJob && (
        <div className="rounded-xl border border-slate-800 p-3">
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="font-medium text-slate-200">Status</span>
            <span className={STATUS_COLOR[activeJob.status] ?? 'text-slate-400'}>{activeJob.status}</span>
          </div>
          {activeJob.status === 'failed' && activeJob.error && <div className="mt-1 text-xs text-rose-300">{activeJob.error}</div>}
          {activeJob.status === 'done' && activeJob.result && (
            <>
              <div className="muted mt-1 whitespace-pre-wrap text-xs leading-relaxed">{plainText(String(activeJob.result.summary ?? ''))}</div>
              <button className="mt-2 flex w-full items-center justify-center gap-1 !py-1 !text-xs" onClick={openReport}>
                <FileText size={12} /> Open Report
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
