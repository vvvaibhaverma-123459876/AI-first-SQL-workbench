import { AuthGate } from './components/auth/AuthGate'
import { WorkspaceShell } from './components/workspace/WorkspaceShell'

export default function App() {
  return (
    <AuthGate>
      <WorkspaceShell />
    </AuthGate>
  )
}
