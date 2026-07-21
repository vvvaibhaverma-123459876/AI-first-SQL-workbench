import { ChevronDown, ChevronRight, File, Folder, FolderPlus, FilePlus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useFileStore } from '../../store/useFileStore'
import type { FileNode } from '../../types'

function children(files: FileNode[], parentId: string | null): FileNode[] {
  return files.filter((f) => f.parent_id === parentId)
}

function TreeNode({ workspaceId, node, depth }: { workspaceId: string; node: FileNode; depth: number }) {
  const { files, openFile, activeTabId, deleteFile, createFile } = useFileStore()
  const [expanded, setExpanded] = useState(true)
  const kids = node.is_folder ? children(files, node.id) : []

  const handleClick = () => {
    if (node.is_folder) setExpanded((e) => !e)
    else openFile(workspaceId, node.id)
  }

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirm(`Delete "${node.name}"${node.is_folder ? ' and everything inside it' : ''}?`)) {
      deleteFile(workspaceId, node.id)
    }
  }

  const handleAddChild = async (e: React.MouseEvent, isFolder: boolean) => {
    e.stopPropagation()
    const name = prompt(isFolder ? 'Folder name' : 'File name (e.g. query.sql)')
    if (name) await createFile(workspaceId, { name, parentId: node.id, isFolder })
  }

  return (
    <div>
      <div
        className="group flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-1 text-sm hover:bg-slate-800/60"
        style={{ paddingLeft: `${depth * 14 + 6}px` }}
        onClick={handleClick}
      >
        {node.is_folder ? (
          expanded ? <ChevronDown size={13} className="shrink-0 text-slate-500" /> : <ChevronRight size={13} className="shrink-0 text-slate-500" />
        ) : (
          <span className="w-[13px]" />
        )}
        {node.is_folder ? <Folder size={14} className="shrink-0 text-blue-400" /> : <File size={14} className="shrink-0 text-slate-400" />}
        <span className={`truncate ${activeTabId === node.id ? 'text-blue-300' : 'text-slate-200'}`}>{node.name}</span>
        <span className="ml-auto hidden shrink-0 items-center gap-1 group-hover:flex">
          {node.is_folder && (
            <>
              <button className="!border-0 !bg-transparent !p-0.5" title="New file" onClick={(e) => handleAddChild(e, false)}>
                <FilePlus size={12} />
              </button>
              <button className="!border-0 !bg-transparent !p-0.5" title="New folder" onClick={(e) => handleAddChild(e, true)}>
                <FolderPlus size={12} />
              </button>
            </>
          )}
          <button className="!border-0 !bg-transparent !p-0.5 hover:!text-rose-400" title="Delete" onClick={handleDelete}>
            <Trash2 size={12} />
          </button>
        </span>
      </div>
      {node.is_folder && expanded && kids.map((child) => <TreeNode key={child.id} workspaceId={workspaceId} node={child} depth={depth + 1} />)}
    </div>
  )
}

export function FileTree({ workspaceId }: { workspaceId: string }) {
  const { files, createFile } = useFileStore()
  const roots = children(files, null)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-2 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Files</span>
        <div className="flex gap-1">
          <button
            className="!border-0 !bg-transparent !p-1"
            title="New file"
            onClick={async () => {
              const name = prompt('File name (e.g. query.sql)')
              if (name) await createFile(workspaceId, { name, parentId: null })
            }}
          >
            <FilePlus size={13} />
          </button>
          <button
            className="!border-0 !bg-transparent !p-1"
            title="New folder"
            onClick={async () => {
              const name = prompt('Folder name')
              if (name) await createFile(workspaceId, { name, parentId: null, isFolder: true })
            }}
          >
            <FolderPlus size={13} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {roots.length === 0 ? (
          <div className="muted px-3 py-4 text-xs">No files yet. Create one above.</div>
        ) : (
          roots.map((node) => <TreeNode key={node.id} workspaceId={workspaceId} node={node} depth={0} />)
        )}
      </div>
    </div>
  )
}
