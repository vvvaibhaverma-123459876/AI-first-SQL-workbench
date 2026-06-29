import Editor from '@monaco-editor/react'
import { Bot, Copy, Play, Save, Sparkles, Wand2, Wrench, X } from 'lucide-react'
import { useState } from 'react'
import { useStudioStore } from '../store/useStudioStore'

const DEMO_PROMPTS = [
  'Top 20 users by total transaction amount',
  'Which referral channel has the best card activation rate?',
  'Monthly revenue trend for the last 6 months',
  'Users with open support tickets and their total spend',
  'Average days to first transaction by country',
]

export function EditorPanel() {
  const {
    tabs,
    activeTabId,
    setActiveTab,
    setSQL,
    addTab,
    runSQL,
    validateSQL,
    generateSQL,
    runAssistant,
    explainSQL,
    repairSQL,
    saveCurrentQuery,
    aiPrompt,
    setAiPrompt,
    loading,
    assistantLoading,
  } = useStudioStore()

  const [saveMode, setSaveMode] = useState(false)
  const [saveName, setSaveName] = useState('')

  const current = tabs.find((tab) => tab.id === activeTabId)
  const busy = loading || assistantLoading

  const handleSave = () => {
    if (!saveName.trim()) return
    saveCurrentQuery(saveName.trim())
    setSaveName('')
    setSaveMode(false)
  }

  return (
    <div className="panel flex h-full flex-col p-4">
      {/* Tabs */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {tabs.map((tab) => (
          <button key={tab.id} className={`text-xs ${tab.id === activeTabId ? '!border-blue-600 !bg-blue-900/40 !text-blue-300' : ''}`} onClick={() => setActiveTab(tab.id)}>
            {tab.title}
          </button>
        ))}
        <button className="text-xs" onClick={addTab}>+ Tab</button>
      </div>

      {/* AI Prompt */}
      <div className="mb-3">
        <div className="relative">
          <textarea
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            className="w-full resize-none pr-8 text-sm"
            rows={2}
            placeholder="Ask in plain English — e.g. Which referral channel has the best card activation rate?"
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); runAssistant() } }}
          />
          {aiPrompt && (
            <button className="absolute right-2 top-2 border-0 bg-transparent p-0 text-slate-500 hover:text-slate-300" onClick={() => setAiPrompt('')}>
              <X size={13} />
            </button>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {DEMO_PROMPTS.map((p) => (
            <button key={p} className="border-slate-700/60 bg-slate-800/60 px-2 py-0.5 text-[11px] text-slate-400 hover:text-slate-200" onClick={() => setAiPrompt(p)}>
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Action buttons */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button disabled={busy} onClick={runAssistant} className="!border-blue-700 !bg-blue-800/60 !text-blue-200 hover:!bg-blue-700">
          <Bot size={14} className="mr-1 inline" />
          {assistantLoading ? 'Thinking…' : 'Ask + Run'}
        </button>
        <button disabled={busy} onClick={runSQL} className="!border-emerald-800 !bg-emerald-900/40 !text-emerald-300 hover:!bg-emerald-800/60">
          <Play size={14} className="mr-1 inline" />
          {loading ? 'Running…' : 'Run SQL'}
          <span className="ml-1 text-[10px] opacity-50">⌘↵</span>
        </button>
        <button disabled={assistantLoading} onClick={generateSQL}>
          <Sparkles size={14} className="mr-1 inline" />Generate
        </button>
        <button onClick={explainSQL}><Wand2 size={14} className="mr-1 inline" />Explain</button>
        <button onClick={repairSQL}><Wrench size={14} className="mr-1 inline" />Fix</button>
        <button onClick={validateSQL}>Format</button>
        <button onClick={() => navigator.clipboard.writeText(current?.sql ?? '')}><Copy size={14} className="mr-1 inline" />Copy</button>
        <button onClick={() => setSaveMode((v) => !v)}><Save size={14} className="mr-1 inline" />Save</button>
      </div>

      {/* Inline save bar */}
      {saveMode && (
        <div className="mb-3 flex gap-2">
          <input
            autoFocus
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="Query name…"
            className="flex-1 text-sm"
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setSaveMode(false) }}
          />
          <button className="!border-emerald-800 !bg-emerald-900/40 !text-emerald-300" onClick={handleSave}>Save</button>
          <button onClick={() => setSaveMode(false)}>Cancel</button>
        </div>
      )}

      {/* Monaco Editor */}
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-800">
        {busy && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-950/60 backdrop-blur-sm">
            <div className="flex items-center gap-3 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-300">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-blue-400" />
              {assistantLoading ? 'AI is generating SQL…' : 'Executing query…'}
            </div>
          </div>
        )}
        <Editor
          height="100%"
          defaultLanguage="sql"
          value={current?.sql ?? ''}
          theme="vs-dark"
          onChange={(value) => setSQL(value ?? '')}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            lineNumbers: 'on',
            renderLineHighlight: 'gutter',
          }}
          onMount={(editor, monaco) => {
            editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runSQL())
          }}
        />
      </div>
    </div>
  )
}
