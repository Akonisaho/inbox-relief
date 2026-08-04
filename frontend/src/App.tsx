import { useState } from 'react'
import { Shell, type View } from './components/Shell'
import { DigestView } from './components/DigestView'
import { InboxView } from './components/InboxView'
import { ChatPanel } from './components/ChatPanel'
import { RulesPanel } from './components/RulesPanel'

function App() {
  const [view, setView] = useState<View>('digest')

  return (
    <Shell active={view} onNavigate={setView}>
      {view === 'digest' && <DigestView />}
      {view === 'inbox' && <InboxView />}
      {view === 'chat' && <ChatPanel />}
      {view === 'rules' && <RulesPanel />}
    </Shell>
  )
}

export default App
