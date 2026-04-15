import Editor from '@monaco-editor/react'
import { Copy, Play, Save, Sparkles, Wand2, Wrench } from 'lucide-react'
import { useStudioStore } from '../store/useStudioStore'

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
    explainSQL,
    repairSQL,
    saveCurrentQuery,
    aiPrompt,
    setAiPrompt,
  } = useStudioStore()

  const current = tabs.find((tab) => tab.id === activeTabId)

  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {tabs.map((tab) => (
          <button key={tab.id} className={tab.id === activeTabId ? '!bg-blue-700' : ''} onClick={() => setActiveTab(tab.id)}>{tab.title}</button>
        ))}
        <button onClick={addTab}>+ New Tab</button>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button onClick={runSQL}><Play size={14} className="mr-1 inline" />Run</button>
        <button onClick={generateSQL}><Sparkles size={14} className="mr-1 inline" />Generate SQL</button>
        <button onClick={explainSQL}><Wand2 size={14} className="mr-1 inline" />Explain</button>
        <button onClick={repairSQL}><Wrench size={14} className="mr-1 inline" />Fix</button>
        <button onClick={validateSQL}>Format / Validate</button>
        <button onClick={() => navigator.clipboard.writeText(current?.sql ?? '')}><Copy size={14} className="mr-1 inline" />Copy</button>
        <button onClick={() => saveCurrentQuery(window.prompt('Saved query name') || 'Untitled Query')}><Save size={14} className="mr-1 inline" />Save</button>
      </div>

      <textarea value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)} className="mb-3 w-full" rows={2} placeholder="Ask AI to generate SQL or suggest relevant tables..." />

      <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-800">
        <Editor
          height="100%"
          defaultLanguage="sql"
          value={current?.sql ?? ''}
          theme="vs-dark"
          onChange={(value) => setSQL(value ?? '')}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: 'on',
            scrollBeyondLastLine: false,
          }}
          onMount={(editor, monaco) => {
            editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runSQL())
          }}
        />
      </div>
    </div>
  )
}
