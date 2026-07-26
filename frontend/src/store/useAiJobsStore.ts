import { create } from 'zustand'
import api from '../services/api'
import type { AiJob } from '../types'
import { useAuthStore } from './useAuthStore'

const POLL_INTERVAL_MS = 1500
// investigate's server-side job_timeout is 900s (app/ai_jobs/service.py) --
// cap polling somewhat past that rather than forever, so a stuck/orphaned
// job (worker crash, RQ work-horse killed without updating the row) shows
// a clear message instead of spinning in "running" indefinitely.
const MAX_POLL_ATTEMPTS = 700

function authHeaders() {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

type AiJobsState = {
  activeJob: AiJob | null
  investigating: boolean
  error: string | null
  startInvestigation: (workspaceId: string, question: string) => Promise<void>
  reset: () => void
}

// Investigate jobs run 45-100s+ (task #22's benchmark, a multi-step chain
// of real local-model calls) -- module-level so a re-render or remount of
// the panel doesn't leak a duplicate poll loop.
let pollTimer: ReturnType<typeof setTimeout> | null = null

export const useAiJobsStore = create<AiJobsState>((set) => ({
  activeJob: null,
  investigating: false,
  error: null,

  startInvestigation: async (workspaceId, question) => {
    if (pollTimer) clearTimeout(pollTimer)
    set({ investigating: true, error: null, activeJob: null })

    let jobId: string
    try {
      const { data } = await api.post<AiJob>(
        `/workspaces/${workspaceId}/ai/jobs`,
        { task_type: 'investigate', input: { question } },
        { headers: authHeaders() },
      )
      jobId = data.id
      set({ activeJob: data })
    } catch {
      set({ investigating: false, error: 'Could not start the investigation.' })
      return
    }

    let attempts = 0
    const poll = async () => {
      attempts += 1
      try {
        const { data: job } = await api.get<AiJob>(`/workspaces/${workspaceId}/ai/jobs/${jobId}`, { headers: authHeaders() })
        set({ activeJob: job })
        if (job.status === 'done' || job.status === 'failed') {
          set({ investigating: false })
          return
        }
      } catch {
        set({ investigating: false, error: 'Lost connection while checking investigation status.' })
        return
      }
      if (attempts >= MAX_POLL_ATTEMPTS) {
        set({ investigating: false, error: 'This investigation is taking much longer than expected. Check back later, or try again.' })
        return
      }
      pollTimer = setTimeout(poll, POLL_INTERVAL_MS)
    }
    pollTimer = setTimeout(poll, POLL_INTERVAL_MS)
  },

  reset: () => {
    if (pollTimer) clearTimeout(pollTimer)
    set({ activeJob: null, investigating: false, error: null })
  },
}))
