import { useEffect, useState } from 'react'
import './App.css'
import heroPhoto from './assets/nova-hero-photo.png'

function MicIcon() {
  return (
    <svg
      width="21"
      height="21"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
      <path d="M12 17.5V21" />
      <path d="M8.5 21h7" />
    </svg>
  )
}

function HomeIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
      <path d="M9.5 21v-6h5v6" />
    </svg>
  )
}

function ChatIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v7A2.5 2.5 0 0 1 17.5 15H10l-5 4v-4.5A2.5 2.5 0 0 1 4 12z" />
    </svg>
  )
}

function SettingsIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 1.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-2.6V20a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1-1.8-1.8.1-.1A1.7 1.7 0 0 0 8 15a1.7 1.7 0 0 0-1.6-1H6v-2.6h.4A1.7 1.7 0 0 0 8 10a1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.8-1.8.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h2.6V5a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.8 1.8-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.4V14h-.4a1.7 1.7 0 0 0-1.6 1z" />
    </svg>
  )
}

function FolderIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <path d="M3.5 7.5A2.5 2.5 0 0 1 6 5h4l2 2h6.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z" />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <path d="M6 3.5h8l4 4V20H6z" />
      <path d="M14 3.5V8h4" />
    </svg>
  )
}

function CalendarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <rect x="4" y="5" width="16" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M4 10h16" />
    </svg>
  )
}

function GridIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="4" width="6" height="6" rx="1" />
      <rect x="4" y="14" width="6" height="6" rx="1" />
      <rect x="14" y="14" width="6" height="6" rx="1" />
    </svg>
  )
}

function AccountIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round">
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 20c.7-3.5 3-5.5 6.5-5.5s5.8 2 6.5 5.5" />
    </svg>
  )
}

function App() {
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('nova-sidebar-width')
    return saved ? Number(saved) : 207
  })

const [task, setTask] = useState('')
  const [activeSection, setActiveSection] = useState('home')

  const [running, setRunning] = useState(false)
  const [backendOnline, setBackendOnline] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')

const [darkMode, setDarkMode] = useState(() => {
  return localStorage.getItem('nova-theme') === 'dark'
})

useEffect(() => {
  localStorage.setItem('nova-theme', darkMode ? 'dark' : 'light')
}, [darkMode])

  useEffect(() => {
    localStorage.setItem('nova-sidebar-width', sidebarWidth)
  }, [sidebarWidth])

  const resizeSidebar = (event) => {
    event.preventDefault()

    const startX = event.clientX
    const startWidth = sidebarWidth

    const handleMove = (moveEvent) => {
      const nextWidth = Math.min(280, Math.max(170, startWidth + (moveEvent.clientX - startX)))
      setSidebarWidth(nextWidth)
    }

    const handleUp = () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
  }

  const runTask = async () => {
    const command = task.trim()
    if (!command || running) return

    // Behave like a chat composer: once the message is submitted,
    // immediately clear the input so it is ready for the next message.
    setTask('')
    setStatusMessage('Starting NOVA…')
    try {
      const response = await fetch('http://127.0.0.1:8000/api/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.error || 'Could not start the task')
      }

      setRunning(true)
      setBackendOnline(true)
      setStatusMessage('NOVA is working…')
    } catch (error) {
      console.error(error)
      setBackendOnline(false)
      setStatusMessage('Backend offline — start api.py')
    }
  }

  const stopTask = async () => {
    try {
      await fetch('http://127.0.0.1:8000/api/stop', { method: 'POST' })
      setStatusMessage('Stopping…')
    } catch (error) {
      console.error(error)
    }
  }

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/status')
        if (!response.ok) throw new Error('Backend unavailable')
        const data = await response.json()
        setBackendOnline(true)
        setRunning(Boolean(data.running))
        if (!data.running && statusMessage === 'NOVA is working…') {
          setStatusMessage('')
        }
      } catch {
        setBackendOnline(false)
        setRunning(false)
      }
    }

    checkBackend()
    const timer = setInterval(checkBackend, 1000)
    return () => clearInterval(timer)
  }, [statusMessage])

  return (
<div
  className={`app ${darkMode ? 'dark-mode' : ''}`}
      style={{
        '--sidebar-width': `${sidebarWidth}px`,
      }}
    >

      {/* ================= SIDEBAR ================= */}

      <aside className="sidebar">

        <svg
          className="sidebar-curves"
          viewBox="0 0 207 700"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            className="sidebar-curve-back"
            d="
              M0 420
              C45 444 82 470 104 510
              C129 556 138 595 207 624
              L207 700
              L0 700Z
            "
          />

          <path
            className="sidebar-curve-front"
            d="
              M0 665
              C17 627 57 614 94 622
              C145 633 171 677 207 713
              L207 700
              L0 700Z
            "
          />
        </svg>

        <div className="brand">
          <div className="nova-logo">
            <span></span>
          </div>

          <span className="nova-text">
            N O V A
          </span>
        </div>

        <nav className="navigation">

          <button className={`nav-item ${activeSection === 'home' ? 'active' : ''}`} onClick={() => setActiveSection('home')}>
            <span className="nav-icon">
              <HomeIcon />
            </span>
            <span>Home</span>
          </button>

          <button className={`nav-item ${activeSection === 'chat' ? 'active' : ''}`} onClick={() => setActiveSection('chat')}>
            <span className="nav-icon">
              <ChatIcon />
            </span>
            <span>Chat</span>
          </button>

          <button className={`nav-item ${activeSection === 'accounts' ? 'active' : ''}`} onClick={() => setActiveSection('accounts')}>
            <span className="nav-icon">
              <AccountIcon />
            </span>
            <span>Accounts</span>
          </button>

          <button className={`nav-item ${activeSection === 'settings' ? 'active' : ''}`} onClick={() => setActiveSection('settings')}>
            <span className="nav-icon">
              <SettingsIcon />
            </span>
            <span>Settings</span>
          </button>

        </nav>

        {/* Drag handle — resize the sidebar directly */}
        <div
          className="sidebar-resize-handle"
          onPointerDown={resizeSidebar}
          role="separator"
          aria-label="Resize sidebar"
          aria-orientation="vertical"
        />

        <div className="sidebar-bottom">

          <div className="bottom-line"></div>

          <div className="bottom-profile">
            <div className="mini-logo"></div>

            <p>
              A more<br />
              capable you.
            </p>
          </div>

        </div>

      </aside>


      {/* ================= MAIN ================= */}

      <main className="main">

        {/* Photo */}

        <div className="hero-image">
          <img src={heroPhoto} alt="" />
        </div>


        {/* Organic main curve */}

        <svg
          className="organic-main"
          viewBox="0 0 1329 620"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <filter
              id="curveShadow"
              x="-20%"
              y="-20%"
              width="140%"
              height="140%"
            >
              <feDropShadow
                dx="0"
                dy="4"
                stdDeviation="9"
                floodColor="#26312f"
                floodOpacity=".12"
              />
            </filter>
          </defs>

          <path
            filter="url(#curveShadow)"
            d="
              M0 0
              L520 0

              C521 91
                539 163
                581 224

              C626 290
                695 334
                772 371

              C852 409
                916 438
                958 477

              C983 501
                995 530
                1000 620

              L0 620
              Z
            "
          />
        </svg>


        {/* Top right */}

        <div className="top-controls">

<button
  className="theme-button"
  onClick={() => setDarkMode(!darkMode)}
  aria-label="Toggle dark mode"
>
  {darkMode ? '☾' : '☼'}
</button>

          <div className="profile-button">
            O
          </div>

        </div>


        {/* Photo message */}

        <div className="image-message">

          <div className="message-line"></div>

          <div>
            <span>See.</span>
            <span>Understand.</span>
            <span>Act.</span>
            <span>For you.</span>
          </div>

        </div>


        {/* ================= MAIN CONTENT ================= */}

        {activeSection === 'home' ? (
        <section className="hero">

          <p className="eyebrow">
            YOUR COMPUTER. AMPLIFIED.
          </p>

          <h1>
            Hello,<br />
            <span>Omkar.</span>
          </h1>

          <p className="hero-description">
            Tell me what you want to do.<br />
            I'll take care of the rest.
          </p>


          {/* Command bar */}

          <div className="task-box">

            <button className="plus-button">
              +
            </button>

            <input
              value={task}
              onChange={(e) => setTask(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') runTask()
              }}
              placeholder="Ask me to do anything..."
            />

            <button className="microphone" aria-label="Voice input">
              <MicIcon />
            </button>

            <button
              className="send-button"
              onClick={running ? stopTask : runTask}
              aria-label={running ? 'Stop task' : 'Send task'}
              title={running ? 'Stop task' : 'Run task'}
            >
              {running ? '■' : '↑'}
            </button>

          </div>

          <div className={`backend-status ${backendOnline ? 'online' : ''} ${statusMessage ? 'visible' : ''}`}>
            <span className="backend-dot"></span>
            <span>{statusMessage || (backendOnline ? 'NOVA backend ready' : 'Backend not connected')}</span>
          </div>


          {/* Quick actions */}

          <div className="suggestions">

            <button onClick={() => setTask('Clean up my downloads')}>
              <FolderIcon />
              Clean up my downloads
            </button>

            <button onClick={() => setTask('Summarize this document')}>
              <FileIcon />
              Summarize this document
            </button>

            <button onClick={() => setTask('Plan my day')}>
              <CalendarIcon />
              Plan my day
            </button>

            <button onClick={() => setTask('Open my design app')}>
              <GridIcon />
              Open my design app
            </button>

          </div>


          {/* Cards */}

          <section className="cards">

            <div className="card card-one">

              <div className="card-top">

                <div>
                  <span className="card-label">
                    GET THINGS DONE
                  </span>

                  <h2>
                    From thought<br />
                    to action.
                  </h2>
                </div>

                <div className="card-icon">
                  ▣
                </div>

              </div>

              <div className="card-bottom">

                <div className="card-line"></div>

                <p>
                  Your computer, on your terms.
                </p>

              </div>

            </div>


            <div className="card card-two">

              <div className="card-top">

                <div>
                  <span className="card-label">
                    WORKS IN YOUR CONTEXT
                  </span>

                  <h2>
                    Understands<br />
                    what you mean.
                  </h2>
                </div>

                <div className="card-icon">
                  ◈
                </div>

              </div>

              <div className="card-bottom">

                <div className="card-line"></div>

                <p>
                  Across your files, apps and the web.
                </p>

              </div>

            </div>


            <div className="card card-three">

              <div className="card-top">

                <div>
                  <span className="card-label">
                    PRIVACY FIRST
                  </span>

                  <h2>
                    Your data<br />
                    stays yours.
                  </h2>
                </div>

                <div className="card-icon">
                  ♙
                </div>

              </div>

              <div className="card-bottom">

                <div className="card-line"></div>

                <p>
                  Local, secure, and always under your control.
                </p>

              </div>

            </div>

          </section>

        </section>
        ) : activeSection === 'accounts' ? (
          <section className="section-page accounts-page">
            <p className="eyebrow">CONNECTED SERVICES</p>
            <h1>Accounts.</h1>
            <p className="section-description">
              Connect the services NOVA can work with on your behalf.
            </p>

            <div className="account-grid">
              <div className="account-card">
                <div className="account-card-icon google-icon">G</div>
                <div className="account-card-copy">
                  <h2>Google</h2>
                  <p>Gmail, Drive, Docs, Calendar and YouTube.</p>
                </div>
                <button className="account-connect">Connect</button>
              </div>

              <div className="account-card">
                <div className="account-card-icon microsoft-icon">M</div>
                <div className="account-card-copy">
                  <h2>Microsoft</h2>
                  <p>Outlook, OneDrive, Teams and Microsoft 365.</p>
                </div>
                <button className="account-connect">Connect</button>
              </div>

              <div className="account-card">
                <div className="account-card-icon apple-icon"></div>
                <div className="account-card-copy">
                  <h2>Apple</h2>
                  <p>Apple services and your connected devices.</p>
                </div>
                <button className="account-connect">Connect</button>
              </div>

              <div className="account-card">
                <div className="account-card-icon browser-icon">◎</div>
                <div className="account-card-copy">
                  <h2>Browser profile</h2>
                  <p>Use NOVA's separate Brave profile for web tasks.</p>
                </div>
                <span className="account-ready">Ready</span>
              </div>
            </div>

            <div className="account-note">
              <span className="account-note-dot"></span>
              <span>Accounts will be connected only when you choose to connect them.</span>
            </div>
          </section>
        ) : activeSection === 'chat' ? (
          <section className="section-page placeholder-page">
            <p className="eyebrow">YOUR CONVERSATIONS</p>
            <h1>Chat.</h1>
            <p className="section-description">Your NOVA conversations will appear here.</p>
          </section>
        ) : (
          <section className="section-page placeholder-page">
            <p className="eyebrow">NOVA PREFERENCES</p>
            <h1>Settings.</h1>
            <p className="section-description">Customize how NOVA looks and works.</p>
          </section>
        )}

      </main>

    </div>
  )
}

export default App