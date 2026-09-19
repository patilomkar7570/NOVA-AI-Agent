import { useEffect, useRef, useState } from 'react'
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


function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('nova-sidebar-collapsed') === 'true')

  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('nova-sidebar-width')
    return saved ? Number(saved) : 207
  })

const [task, setTask] = useState('')
  const [activeSection, setActiveSection] = useState('home')
  const [profileOpen, setProfileOpen] = useState(false)
  const [userName, setUserName] = useState(() => localStorage.getItem('nova-user-name') || 'Omkar')
  const [nameDraft, setNameDraft] = useState(() => localStorage.getItem('nova-user-name') || 'Omkar')
  const profileRef = useRef(null)
  const [running, setRunning] = useState(false)
  const [stopArmed, setStopArmed] = useState(false)
  const [backendOnline, setBackendOnline] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const [events, setEvents] = useState([])

const [themeMode, setThemeMode] = useState(() => localStorage.getItem('nova-theme') || 'system')
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)
  const darkMode = themeMode === 'dark' || (themeMode === 'system' && systemDark)

  useEffect(() => {
    localStorage.setItem('nova-theme', themeMode)
  }, [themeMode])

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!media) return
    const updateSystemTheme = (event) => setSystemDark(event.matches)
    setSystemDark(media.matches)
    media.addEventListener?.('change', updateSystemTheme)
    return () => media.removeEventListener?.('change', updateSystemTheme)
  }, [])

  useEffect(() => {
    localStorage.setItem('nova-sidebar-width', sidebarWidth)
  }, [sidebarWidth])

  useEffect(() => {
    localStorage.setItem('nova-sidebar-collapsed', sidebarCollapsed)
  }, [sidebarCollapsed])

  const getInitials = (name) => {
    const words = name.trim().split(/\s+/).filter(Boolean)
    if (!words.length) return 'O'
    return words.slice(0, 2).map(word => word[0].toUpperCase()).join('')
  }

  const getChatInitials = (title) => {
    const words = String(title || 'Chat').trim().split(/\s+/).filter(Boolean)
    if (!words.length) return 'C'
    if (words.length === 1) return words[0].slice(0, 3).toUpperCase()
    return words.slice(0, 3).map(word => word[0].toUpperCase()).join('')
  }

  const getFirstName = (name) => {
    return name.trim().split(/\s+/).filter(Boolean)[0] || ''
  }

  const updateUserName = (name) => {
    setNameDraft(name)
    setUserName(name)
    localStorage.setItem('nova-user-name', name)
  }

  const openProfile = () => {
    setNameDraft(userName)
    setProfileOpen(!profileOpen)
  }

  useEffect(() => {
    if (!profileOpen) return

    const handlePointerDown = (event) => {
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setProfileOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [profileOpen])

  const resizeSidebar = (event) => {
    event.preventDefault()

    const startX = event.clientX
    const startWidth = sidebarCollapsed ? 72 : sidebarWidth

    const handleMove = (moveEvent) => {
      // The resize handle is now the only way to collapse/expand the sidebar.
      // Drag all the way down to 72px to enter compact mode.
      const rawWidth = startWidth + (moveEvent.clientX - startX)
      const nextWidth = Math.min(280, Math.max(72, rawWidth))

      if (nextWidth <= 90) {
        setSidebarCollapsed(true)
        setSidebarWidth(72)
      } else {
        setSidebarCollapsed(false)
        setSidebarWidth(nextWidth)
      }
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

  const loadChats = async (selectLatest = false) => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/chats')

      if (!response.ok) {
        throw new Error('Could not load chat history')
      }

      const data = await response.json()
      const nextChats = Array.isArray(data.chats) ? data.chats : []

      setChats(nextChats)

      // On first load, open the newest saved conversation.
      // Otherwise keep whichever conversation the user is currently viewing.
      if (selectLatest && nextChats.length && !activeChatId) {
        setActiveChatId(nextChats[0].id)
      }
    } catch (error) {
      console.error('Chat history:', error)
    }
  }

  const createNewChat = (event) => {
    if (event) event.preventDefault()
    if (running) return

    // Start a fresh conversation directly in the Chat screen.
    // The backend chat is created only when the first message is sent.
    setActiveChatId(null)
    setActiveSection('chat')
    setTask('')
    setEvents([])
    setStatusMessage('')
  }

  const openChat = (chatId) => {
    setActiveChatId(chatId)
    setActiveSection('chat')
  }

  const activeChat = chats.find((chat) => chat.id === activeChatId) || null

  const deleteChat = async (chatId) => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/chats/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId }),
      })

      if (!response.ok) {
        throw new Error('Could not delete chat')
      }

      const data = await response.json()

      setChats(Array.isArray(data.chats) ? data.chats : [])

      if (activeChatId === chatId) {
        setActiveChatId(null)
      }
    } catch (error) {
      console.error('Delete chat:', error)
      setStatusMessage('Could not delete chat.')
    }
  }

  const savePromptToHistory = async (command) => {
    try {
      // No active chat = the Home composer is starting a brand-new conversation.
      if (!activeChatId) {
        const response = await fetch('http://127.0.0.1:8000/api/chats', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command }),
        })

        if (!response.ok) {
          throw new Error('Could not create chat')
        }

        const data = await response.json()
        const createdChat = data.chat

        setChats((current) => [
          createdChat,
          ...current.filter((chat) => chat.id !== createdChat.id),
        ])

        setActiveChatId(createdChat.id)

        return {
          chatId: createdChat.id,
          createdNewChat: true,
        }
      }

      // Active chat = continue the existing conversation.
      const response = await fetch(
        'http://127.0.0.1:8000/api/chats/append',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: activeChatId,
            command,
          }),
        }
      )

      if (!response.ok) {
        throw new Error('Could not save message')
      }

      const data = await response.json()

      setChats((current) =>
        current.map((chat) =>
          chat.id === activeChatId ? data.chat : chat
        )
      )

      return {
        chatId: activeChatId,
        createdNewChat: false,
      }
    } catch (error) {
      console.error('Chat history save:', error)
      return null
    }
  }

  const runTask = async (commandOverride = null) => {
    const command = (commandOverride ?? task).trim()

    if (!command || running) return

    setTask('')
    setEvents([])
    setStopArmed(false)

    // A message from Home immediately opens the conversation screen.
    // The first message creates the backend chat in the background.
    const startedFromHome = activeSection === 'home' && !activeChatId
    if (startedFromHome) {
      setActiveSection('chat')
    }

    setStatusMessage('Starting conversation…')

    const saved = await savePromptToHistory(command)

    if (!saved) {
      setStatusMessage('Could not save chat history.')
      return
    }

    // If the prompt came from Home, this was a new conversation.
    // Immediately move into the Chat screen so the conversation continues there.
    if (saved.createdNewChat) {
      setActiveSection('chat')
    }

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
      setStatusMessage('Backend offline — start api.py')
    }
  }

  const handleActionButton = async () => {
    // Same two-stage behavior as the old keyboard ESC control:
    // 1st press = stop the current task.
    // 2nd press = close the NOVA browser worker.
    if (running) {
      try {
        await fetch('http://127.0.0.1:8000/api/stop', { method: 'POST' })
        setStopArmed(true)
        setStatusMessage('Stopping… press again to close NOVA.')
      } catch (error) {
        console.error(error)
        setStatusMessage('Could not stop the task.')
      }
      return
    }

    if (stopArmed) {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/close', { method: 'POST' })
        if (!response.ok) throw new Error('Could not close NOVA')
        setRunning(false)
        setBackendOnline(true)
        setStopArmed(false)
        setStatusMessage('NOVA agent closed.')
      } catch (error) {
        console.error(error)
        setStatusMessage('Could not close NOVA.')
      }
      return
    }

    runTask()
  }

  useEffect(() => {
    loadChats(true)
  }, [])

  useEffect(() => {
    if (activeSection === 'chat') loadChats(false)
  }, [activeSection])

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/status')
        if (!response.ok) throw new Error('Backend unavailable')
        const data = await response.json()
        setBackendOnline(true)
        setRunning(Boolean(data.running))

        try {
          const eventResponse = await fetch('http://127.0.0.1:8000/api/events')
          if (eventResponse.ok) {
            const eventData = await eventResponse.json()
            setEvents(Array.isArray(eventData.events) ? eventData.events.slice(-80) : [])
          }
        } catch (eventError) {
          console.debug('NOVA events:', eventError)
        }

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
        '--sidebar-width': `${sidebarCollapsed ? 72 : sidebarWidth}px`,
      }}
    >

      {/* ================= SIDEBAR ================= */}

      <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${!sidebarCollapsed && sidebarWidth < 180 ? 'compact' : ''}`}>
        <svg
          className="sidebar-curves"
          viewBox="0 0 207 700"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            className="sidebar-curve-back"
            d="M0 420 C45 444 82 470 104 510 C129 556 138 595 207 624 L207 700 L0 700Z"
          />
          <path
            className="sidebar-curve-front"
            d="M0 665 C17 627 57 614 94 622 C145 633 171 677 207 713 L207 700 L0 700Z"
          />
        </svg>

        <div className="sidebar-top">
          <div className="brand">
            <div className="nova-logo"><span></span></div>
            <span className="nova-text">N O V A</span>
          </div>
        </div>

        <div className="sidebar-primary">
          <button
            type="button"
            className={`nav-item ${activeSection === 'home' ? 'active' : ''}`}
            onClick={() => {
              // Home is always the starting point for a NEW conversation.
              // Deselect the current chat so the next Home message creates a fresh chat.
              setActiveChatId(null)
              setActiveSection('home')
              setTask('')
              setEvents([])
              setStatusMessage('')
            }}
          >
            <span className="nav-icon"><HomeIcon /></span>
            <span className="nav-label">Home</span>
          </button>
        </div>

        <div className="sidebar-chats">
          <div className="sidebar-chats-heading">
            <span className="nav-label">Chats</span>
            <span className="chat-count">{chats.length}</span>
          </div>
          <div className="sidebar-chat-list">
            {chats.length === 0 ? (
              <div className="sidebar-chat-empty nav-label">Your conversations will appear here.</div>
            ) : chats.map((chat) => (
              <div className={`sidebar-chat-item ${activeChatId === chat.id ? 'active' : ''}`} key={chat.id}>
                <button type="button" className="sidebar-chat-select" onClick={() => openChat(chat.id)} title={chat.title || 'Chat'}>
                  <span className="sidebar-chat-title">{chat.title || 'Chat'}</span>
                  <span className="sidebar-chat-title-compact">{getChatInitials(chat.title || 'Chat')}</span>
                </button>
                <button type="button" className="sidebar-chat-delete" onClick={() => deleteChat(chat.id)} aria-label={`Delete ${chat.title || 'chat'}`} title="Delete chat">×</button>
              </div>
            ))}
          </div>
        </div>

        <div className="sidebar-bottom">
          <div className="profile-wrap" ref={profileRef}>
            <div className="sidebar-profile-row">
              <button
                type="button"
                className="sidebar-profile-button sidebar-settings-profile-button"
                onClick={() => { setProfileOpen(false); setActiveSection('settings') }}
                aria-label="Open Settings"
                title="Settings"
              >
                <span className="sidebar-profile-avatar">{getInitials(userName)}</span>
                <span className={`profile-inline-settings ${activeSection === 'settings' ? 'active' : ''}`}>
                  <SettingsIcon />
                </span>
                <span className="sidebar-profile-name nav-label">{userName || 'Omkar'}</span>
                <span className="sidebar-profile-more nav-label">•••</span>
              </button>
            </div>

            {profileOpen && (
              <div className="profile-popover">
                <div className="profile-popover-header">
                  <div className="profile-popover-avatar">{getInitials(userName)}</div>
                  <div>
                    <span className="profile-popover-label">ACCOUNT</span>
                    <strong>{userName || 'Omkar'}</strong>
                  </div>
                </div>
                <label className="profile-name-label" htmlFor="nova-name">Your name</label>
                <input id="nova-name" className="profile-name-input" value={nameDraft} onChange={(e) => updateUserName(e.target.value)} placeholder="Enter your name" />
                <button type="button" className="profile-menu-button" onClick={() => { setProfileOpen(false); setActiveSection('settings') }}>
                  <SettingsIcon /><span>Settings</span>
                </button>
                <button type="button" className="profile-menu-button theme-menu-button" onClick={() => setThemeMode(darkMode ? 'light' : 'dark')}>
                  <span className="theme-menu-icon">{darkMode ? '☾' : '☼'}</span>
                  <span>{darkMode ? 'Light mode' : 'Dark mode'}</span>
                </button>
              </div>
            )}
          </div>
        </div>

        <div
          className="sidebar-resize-handle"
          onPointerDown={resizeSidebar}
          role="separator"
          aria-label="Resize sidebar"
          aria-orientation="vertical"
        />
      </aside>


      {/* ================= MAIN ================= */}

      <main className="main">

        {activeSection === 'home' && (
          <>
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
          <path
            d="
              M0 0
              L430 0
              C428 91
                438 163
                475 224
              C520 290
                585 334
                650 371
              C715 409
                765 438
                795 477
              C812 501
                820 530
                825 620
              L0 620
              Z
            "
          />
        </svg>


          </>
        )}


        {activeSection === 'home' && (
          <div className="image-message">

            <div className="message-line"></div>

            <div>
              <span>See.</span>
              <span>Understand.</span>
              <span>Act.</span>
              <span>For you.</span>
            </div>

          </div>
        )}


        {/* ================= MAIN CONTENT ================= */}

        {activeSection === 'home' ? (
        <section className="hero">

          <p className="eyebrow">
            YOUR COMPUTER. AMPLIFIED.
          </p>

          <h1>
            Hello,<br />
            <span>{getFirstName(userName)}.</span>
          </h1>

          <p className="hero-description">
            Tell me what you want to do.<br />
            I'll take care of the rest.
          </p>


          {/* Command bar */}

          <div className="task-box">

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
              onClick={handleActionButton}
              aria-label={running ? 'Stop task' : stopArmed ? 'Close NOVA agent' : 'Send task'}
              title={running || stopArmed ? (stopArmed && !running ? 'Close NOVA agent (press again)' : 'Stop task') : 'Run task'}
            >
              {running || stopArmed ? '■' : '↑'}
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
        ) : activeSection === 'chat' ? (
          <section className="section-page chat-page">
            <div className="chat-page-header">
              <div>
                <p className="eyebrow">{activeChat ? 'CONVERSATION' : 'NEW CONVERSATION'}</p>
                <h1>{activeChat?.title || 'Chat.'}</h1>
              </div>
              <button className="new-chat-button" type="button" onClick={createNewChat}>
                + New chat
              </button>
            </div>

            <div className="chat-conversation-panel chat-conversation-focused chat-workspace">
              {activeChat ? (
                <div className="conversation-messages">
                  {(activeChat.messages || []).map((message, index) => (
                    <div
                      className={`conversation-message ${message.role === 'user' ? 'user' : 'nova'}`}
                      key={`${message.time || 'message'}-${index}`}
                    >
                      <span className="conversation-role">
                        {message.role === 'user' ? 'YOU' : 'NOVA'}
                      </span>
                      <p>{message.content}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="conversation-empty">
                  <div className="conversation-empty-mark">O</div>
                  <h2>Start a new conversation.</h2>
                  <p>Send a message below and NOVA will keep the conversation together.</p>
                </div>
              )}

              {events.length > 0 && (
                <div className="nova-live-activity" aria-live="polite" style={{
                  margin: '0 auto 16px',
                  width: 'min(860px, calc(100% - 48px))',
                  padding: '14px 16px',
                  borderRadius: '18px',
                  border: '1px solid rgba(40, 45, 38, 0.10)',
                  background: 'rgba(255, 255, 255, 0.48)',
                  backdropFilter: 'blur(10px)',
                  WebkitBackdropFilter: 'blur(10px)'
                }}>
                  <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:'9px'}}>
                    <span style={{fontSize:'10px',letterSpacing:'0.14em',fontWeight:700,opacity:0.58}}>LIVE ACTIVITY</span>
                    <span style={{width:'7px',height:'7px',borderRadius:'50%',background:running?'#5f735d':'#92988e',boxShadow:running?'0 0 0 4px rgba(95,115,93,0.12)':'none'}} />
                  </div>
                  <div style={{display:'flex',flexDirection:'column',gap:'7px',maxHeight:'190px',overflowY:'auto'}}>
                    {events.slice(-8).map((event) => (
                      <div key={event.id} style={{display:'flex',alignItems:'flex-start',gap:'9px',fontSize:'12px',lineHeight:1.45,opacity:event.kind==='log'?0.66:0.9}}>
                        <span style={{minWidth:'6px',width:'6px',height:'6px',marginTop:'6px',borderRadius:'50%',background:event.kind==='error'?'#a55c55':(event.kind==='success'||event.kind==='done')?'#668062':'#8b9186'}} />
                        <span>{event.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="task-box chat-task-box">
                <input
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') runTask()
                  }}
                  placeholder={activeChat ? 'Continue this conversation...' : 'Start a new conversation...'}
                />
                <button className="microphone" aria-label="Voice input" type="button">
                  <MicIcon />
                </button>
                <button
                  className="send-button"
                  onClick={handleActionButton}
                  aria-label={running ? 'Stop task' : stopArmed ? 'Close NOVA agent' : 'Send message'}
                  title={running || stopArmed ? (stopArmed && !running ? 'Close NOVA agent (press again)' : 'Stop task') : 'Send message'}
                  type="button"
                >
                  {running || stopArmed ? '■' : '↑'}
                </button>
              </div>
            </div>
          </section>
        ) : (
          <section className="section-page settings-page">
            <p className="eyebrow">NOVA PREFERENCES</p>
            <h1>Settings.</h1>

            <div className="settings-panel">
              <section className="settings-card">
                <div className="settings-card-copy">
                  <span className="settings-card-label">PROFILE</span>
                  <h2>Display name</h2>
                  <p>This name is used across your NOVA interface.</p>
                </div>
                <input
                  className="settings-name-input"
                  value={nameDraft}
                  onChange={(e) => updateUserName(e.target.value)}
                  placeholder="Enter your name"
                  aria-label="Display name"
                />
              </section>

              <section className="settings-card">
                <div className="settings-card-copy">
                  <span className="settings-card-label">APPEARANCE</span>
                  <h2>Theme</h2>
                  <p>Choose how NOVA looks on this device.</p>
                </div>
                <div className="settings-theme-options">
                  <button type="button" className={themeMode === 'light' ? 'selected' : ''} onClick={() => setThemeMode('light')}>
                    ☼ <span>Light</span>
                  </button>
                  <button type="button" className={themeMode === 'dark' ? 'selected' : ''} onClick={() => setThemeMode('dark')}>
                    ☾ <span>Dark</span>
                  </button>
                  <button type="button" className={themeMode === 'system' ? 'selected' : ''} onClick={() => setThemeMode('system')}>
                    ◐ <span>System</span>
                  </button>
                </div>
              </section>

              <section className="settings-card">
                <div className="settings-card-copy">
                  <span className="settings-card-label">SYSTEM</span>
                  <h2>Backend connection</h2>
                  <p>The local NOVA backend must be running for computer tasks.</p>
                </div>
                <div className={`settings-status ${backendOnline ? 'online' : ''}`}>
                  <span className="backend-dot"></span>
                  <span>{backendOnline ? 'Connected' : 'Not connected'}</span>
                </div>
              </section>
            </div>
          </section>
        )}

      </main>

    </div>
  )
}

export default App