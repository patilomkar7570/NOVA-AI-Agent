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


// Turns low-level agent traces into a short, human-readable activity feed.
// It intentionally hides raw JSON/arguments and repetitive internal logs.
function curateActivityEvents(rawEvents = []) {
  if (!Array.isArray(rawEvents)) return []

  const rawText = rawEvents.map((event) => String(event?.message || '')).join('\n')
  const urlMatch = rawText.match(/https?:\/\/[^\s\]}"'<>]+/i)
  let target = ''
  if (urlMatch) {
    try {
      const host = new URL(urlMatch[0].replace(/[),.;]+$/, '')).hostname.replace(/^www\./, '')
      target = host.split('.')[0].replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    } catch { /* Ignore malformed URLs in agent logs. */ }
  }

  const describeAction = (action, message) => {
    const name = String(action || '').toUpperCase()
    const context = target || ''
    if (name === 'OPEN_URL' || name.includes('OPEN_FIRST')) return context ? `Opening ${context}` : 'Opening a webpage'
    if (name.includes('SEARCH')) return context ? `Searching for ${context}` : 'Searching the web'
    if (name.includes('CLICK')) return 'Clicking the relevant page control'
    if (name.includes('TYPE') || name.includes('FILL') || name.includes('INPUT')) return 'Entering information on the page'
    if (name.includes('SCROLL')) return 'Reviewing more of the page'
    if (name.includes('WAIT')) return 'Waiting for the page to respond'
    if (name.includes('EXTRACT') || name.includes('READ') || name.includes('GET_TEXT')) return 'Reading the page content'
    if (name === 'DONE' || name === 'ANSWER') return 'Task completed'
    if (name.includes('NAVIGATE')) return context ? `Navigating to ${context}` : 'Navigating to the requested page'
    return ''
  }

  const curated = []
  const seen = new Set()
  const iconForActivity = (message, kind) => {
    if (kind === 'error') return '⚠️'
    if (kind === 'success' || kind === 'done') return '✅'
    if (kind === 'plan') return '🧭'
    if (/\b(opening|opened|navigating|navigate)\b/i.test(message)) return '🌐'
    if (/\b(searching|search)\b/i.test(message)) return '🔎'
    if (/\b(clicking|click)\b/i.test(message)) return '🖱️'
    if (/\b(entering|typing|filling)\b/i.test(message)) return '⌨️'
    if (/\b(scrolling|reviewing)\b/i.test(message)) return '📜'
    if (/\b(reading|reviewing|content)\b/i.test(message)) return '📖'
    if (/\b(waiting)\b/i.test(message)) return '⏳'
    if (/\b(saved|downloaded)\b/i.test(message)) return '💾'
    return '✨'
  }
  const push = (event, message, kind = 'progress') => {
    const clean = String(message || '').replace(/\s+/g, ' ').trim()
    if (!clean || seen.has(clean.toLowerCase())) return
    seen.add(clean.toLowerCase())
    curated.push({ id: event?.id ?? `${curated.length}-${clean}`, message: clean, kind, icon: iconForActivity(clean, kind) })
  }

  for (const event of rawEvents) {
    const original = String(event?.message || '').trim()
    if (!original) continue
    const kind = String(event?.kind || '').toLowerCase()

    if (kind === 'error' || /\b(error|failed|failure|exception)\b/i.test(original)) {
      const concise = original
        .replace(/^.*?(?:ERROR|EXCEPTION)\s*[:\-]?\s*/i, '')
        .split(/\n|\{\s*['"](?:url|selector|text)['"]\s*:/)[0]
        .replace(/\s+/g, ' ')
        .trim()
      if (concise && concise.length < 220) push(event, concise, 'error')
      else push(event, 'Something went wrong while completing this step.', 'error')
      continue
    }

    // Collapse full planner dumps into a single useful intention.
    if (/\bPLAN\b/i.test(original) && /OPEN_URL|SEARCH_WEB|CLICK|TYPE|SCROLL|DONE/i.test(original)) {
      const action = original.match(/\b(OPEN_URL|OPEN_FIRST_ORGANIC_RESULT|OPEN_FIRST_VIDEO|SEARCH_WEB|CLICK|TYPE|FILL|SCROLL|NAVIGATE)\b/i)?.[1]
      const summary = action ? describeAction(action, original) : ''
      if (summary) push(event, `Plan: ${summary.charAt(0).toLowerCase()}${summary.slice(1)}`, 'plan')
      continue
    }

    // Convert step traces into plain-language milestones.
    const step = original.match(/(?:STEP\s*\d+\s*:\s*|ACTION\s*:\s*)([A-Z][A-Z0-9_]+)/i)
    if (step) {
      const actionName = String(step[1] || '').toUpperCase()
      if (actionName === 'DONE' || actionName === 'ANSWER') {
        push(event, 'Task completed', 'success')
      } else {
        const summary = describeAction(actionName, original)
        if (summary) push(event, summary, 'progress')
      }
      continue
    }

    if (/^\s*(?:DONE|ANSWER)\s*(?:\{.*\})?\s*$/i.test(original) || /⚡\s*STEP\s*\d+\s*:\s*(?:DONE|ANSWER)/i.test(original)) {
      push(event, 'Task completed', 'success')
      continue
    }

    // Hide JSON argument dumps, raw action objects, and internal debug chatter.
    if (/^\s*[{}\[\]]+\s*$/.test(original) || /^\s*\{"?(?:url|selector|text|x|y|button)"?\s*:/.test(original)) continue
    if (/^(?:DEBUG|TRACE|RAW|HTTP\s+\d|REQUEST\s+BODY)\b/i.test(original)) continue

    // Keep only short, user-facing status messages rather than arbitrary logs.
    if (kind === 'success' || kind === 'done' || /\b(completed successfully|task completed|finished successfully)\b/i.test(original)) {
      push(event, 'Task completed', 'success')
    } else if (/\b(opened|navigated to|searching for|found|saved|downloaded|submitted|completed|could not|unable to)\b/i.test(original) && original.length <= 150) {
      push(event, original.replace(/\s+/g, ' '), kind || 'progress')
    }
  }

  // Keep the feed focused on the latest few meaningful milestones.
  return curated.slice(-5)
}

function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('nova-sidebar-collapsed') === 'true')

  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('nova-sidebar-width')
    return saved ? Number(saved) : 207
  })

const [task, setTask] = useState('')
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef(null)
  const [activeSection, setActiveSection] = useState('home')
  const [profileOpen, setProfileOpen] = useState(false)
  const [userName, setUserName] = useState(() => localStorage.getItem('nova-user-name') || 'Omkar')
  const [nameDraft, setNameDraft] = useState(() => localStorage.getItem('nova-user-name') || 'Omkar')
  const profileRef = useRef(null)
  const [running, setRunning] = useState(false)
  // Progress-panel visibility is controlled manually by the user.
  const [stopArmed, setStopArmed] = useState(false)
  const [backendOnline, setBackendOnline] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const chatRevisionRef = useRef(0)
  const [events, setEvents] = useState([])
  // Task panel is hidden while idle. Its expanded/collapsed preference persists between tasks.
  const [taskPanelVisible, setTaskPanelVisible] = useState(false)
  const [activityExpanded, setActivityExpanded] = useState(() => localStorage.getItem('nova-task-panel-expanded') === 'true')
  const [activityHeight, setActivityHeight] = useState(() => {
    const saved = Number(localStorage.getItem('nova-task-panel-height'))
    return Number.isFinite(saved) && saved >= 120 && saved <= 420 ? saved : 190
  })
  const [activityResizing, setActivityResizing] = useState(false)
  const activityResizeRef = useRef(null)
  const taskStartedRef = useRef(false)

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

  useEffect(() => {
    localStorage.setItem('nova-task-panel-expanded', String(activityExpanded))
  }, [activityExpanded])

  useEffect(() => {
    localStorage.setItem('nova-task-panel-height', String(activityHeight))
  }, [activityHeight])

  useEffect(() => {
    if (!activityResizing) return undefined
    const handlePointerMove = (event) => {
      const drag = activityResizeRef.current
      if (!drag) return
      const nextHeight = Math.max(120, Math.min(420, drag.startHeight + drag.startY - event.clientY))
      setActivityHeight(nextHeight)
    }
    const handlePointerUp = () => {
      activityResizeRef.current = null
      setActivityResizing(false)
    }
    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    window.addEventListener('pointercancel', handlePointerUp)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
      window.removeEventListener('pointercancel', handlePointerUp)
    }
  }, [activityResizing])

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
    const requestRevision = chatRevisionRef.current
    try {
      const response = await fetch('http://127.0.0.1:8000/api/chats')

      if (!response.ok) {
        throw new Error('Could not load chat history')
      }

      const data = await response.json()
      const nextChats = Array.isArray(data.chats) ? data.chats : []

      // Do not let an older history response overwrite a chat created or
      // updated while this request was in flight.
      if (requestRevision !== chatRevisionRef.current) return

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
  const curatedEvents = curateActivityEvents(events)

  const deleteChat = async (chatId) => {
    const chatToDelete = chats.find((chat) => String(chat.id) === String(chatId))
    const title = chatToDelete?.title || 'this conversation'
    const confirmed = window.confirm(
      `Permanently delete "${title}"?\n\nThis removes the conversation from NOVA's saved chat history and cannot be undone.`
    )
    if (!confirmed) return

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chats/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId }),
      })

      if (!response.ok) {
        throw new Error('Could not delete chat')
      }

      // Remove only the exact conversation the user selected. Do not replace
      // the whole local history with a possibly incomplete response payload.
      await response.json().catch(() => ({}))

      chatRevisionRef.current += 1
      setChats((current) => current.filter((chat) => String(chat.id) !== String(chatId)))

      if (String(activeChatId) === String(chatId)) {
        setActiveChatId(null)
      }
    } catch (error) {
      console.error('Delete chat:', error)
      setStatusMessage('Could not delete chat.')
    }
  }

  const savePromptToHistory = async (command, forceNewChat = false) => {
    try {
      // Homepage submissions always create a new conversation, regardless of
      // any previously selected chat ID left over from initial history loading.
      if (forceNewChat || !activeChatId) {
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

        chatRevisionRef.current += 1
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

      chatRevisionRef.current += 1
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
    setTaskPanelVisible(true)
    taskStartedRef.current = false
    // Keep the user's saved expanded/collapsed preference; only show the panel.

    // Every submission from Home starts a fresh conversation. A message sent
    // from an already-open conversation continues that conversation instead.
    const startedFromHome = activeSection === 'home'
    const mustCreateNewChat = startedFromHome || !activeChatId
    if (startedFromHome) {
      setActiveChatId(null)
      setActiveSection('chat')
    }

    // Keep the progress panel in the user's chosen state; do not auto-expand it.
    setStatusMessage('Starting conversation…')

    const saved = await savePromptToHistory(command, mustCreateNewChat)

    if (!saved) {
      setStatusMessage('Could not save chat history.')
      setTaskPanelVisible(false)
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

      taskStartedRef.current = true
      setTaskPanelVisible(true)
      setRunning(true)
      setBackendOnline(true)
      setStatusMessage('NOVA is working…')
    } catch (error) {
      console.error(error)
      taskStartedRef.current = false
      setTaskPanelVisible(false)
      setStatusMessage('Backend offline — start api.py')
    }
  }

  // Shared voice handler used by the Home and Chat microphone buttons.
  // It only fills the composer; it never sends or executes a transcript.
  const toggleVoiceInput = () => {
    if (listening) {
      recognitionRef.current?.stop()
      return
    }

    if (running) {
      setStatusMessage('Stop the current task before starting a voice command.')
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition

    if (!SpeechRecognition) {
      setStatusMessage('Speech recognition is not available in this browser. Try a supported version of Microsoft Edge or Brave.')
      return
    }

    try {
      const recognition = new SpeechRecognition()
      recognitionRef.current = recognition
      let finalTranscript = ''

      recognition.lang = 'en-IN'
      recognition.continuous = true
      recognition.interimResults = true
      recognition.maxAlternatives = 1

      recognition.onstart = () => {
        setListening(true)
        setStatusMessage('Listening… speak your command. Click the mic to stop.')
      }

      recognition.onresult = (event) => {
        // Keep final words, while showing interim words live in the input.
        let interimTranscript = ''
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index]
          const words = result?.[0]?.transcript || ''
          if (result.isFinal) {
            finalTranscript = `${finalTranscript} ${words}`.trim()
          } else {
            interimTranscript += ` ${words}`
          }
        }

        const liveTranscript = `${finalTranscript} ${interimTranscript}`.trim()
        if (liveTranscript) setTask(liveTranscript)
      }

      recognition.onerror = (event) => {
        setListening(false)
        const messages = {
          'not-allowed': 'Microphone access was blocked. Allow microphone access for NOVA in your browser settings.',
          'service-not-allowed': 'The browser speech-recognition service is unavailable or blocked.',
          'no-speech': 'No speech was detected. Press the microphone and try again.',
          network: 'Online speech recognition could not connect. Check your internet connection.',
          'audio-capture': 'The browser could not access an audio input device.',
          aborted: ''
        }
        const message = messages[event.error] ?? `Speech recognition failed: ${event.error}.`
        if (message) setStatusMessage(message)
      }

      recognition.onend = () => {
        setListening(false)
        if (recognitionRef.current === recognition) recognitionRef.current = null
        setStatusMessage('Voice input stopped — review or edit the text, then press Send.')
      }

      recognition.start()
    } catch (error) {
      recognitionRef.current = null
      setListening(false)
      console.error('NOVA speech recognition:', error)
      setStatusMessage('Could not start speech recognition. Check browser microphone permissions and try again.')
    }
  }

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort?.()
    }
  }, [])

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
    const checkBackend = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/status')
        if (!response.ok) throw new Error('Backend unavailable')
        const data = await response.json()
        setBackendOnline(true)
        const backendRunning = Boolean(data.running)
        setRunning(backendRunning)
        if (backendRunning) {
          taskStartedRef.current = true
          setTaskPanelVisible(true)
        } else if (taskStartedRef.current) {
          // Hide the panel when the active task finishes; retain its saved size/state.
          taskStartedRef.current = false
          setTaskPanelVisible(false)
        }

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
  data-chat-ui-version="1.7"
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

            <button
              className={`microphone ${listening ? 'voice-listening' : ''}`}
              aria-label={listening ? 'Stop voice input' : 'Start voice input'}
              title={listening ? 'Stop listening' : 'Speak a command'}
              aria-pressed={listening}
              type="button"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                toggleVoiceInput()
              }}
            >
              {listening ? (
                <span className="voice-wave" aria-hidden="true">
                  <i /><i /><i /><i /><i />
                </span>
              ) : <MicIcon />}
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
                      {message.role !== 'user' && (
                        <span className="conversation-role">NOVA</span>
                      )}
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



              {taskPanelVisible && (
                <section
                  className={`nova-live-activity ${activityExpanded ? 'expanded' : 'collapsed'} ${activityResizing ? 'resizing' : ''}`}
                  aria-label="Task progress"
                  aria-live="polite"
                  style={activityExpanded ? { '--nova-activity-height': `${activityHeight}px` } : undefined}
                >
                  {activityExpanded && (
                    <div
                      className="activity-resize-handle"
                      role="separator"
                      aria-orientation="horizontal"
                      aria-label="Resize task progress panel"
                      title="Drag up or down to resize task progress"
                      onPointerDown={(event) => {
                        event.preventDefault()
                        activityResizeRef.current = { startY: event.clientY, startHeight: activityHeight }
                        setActivityResizing(true)
                      }}
                    ><span /></div>
                  )}
                  <button
                    type="button"
                    className="activity-toggle"
                    onClick={() => setActivityExpanded((expanded) => !expanded)}
                    title={activityExpanded ? 'Collapse task progress' : 'Expand task progress'}
                    aria-label={activityExpanded ? 'Collapse task progress details' : 'Expand task progress details'}
                    aria-expanded={activityExpanded}
                    aria-controls="nova-activity-details"
                  >
                    <span className="activity-toggle-copy">
                      <span className="activity-toggle-title">📋 TASK PROGRESS</span>
                      <span className="activity-toggle-status">
                        {statusMessage || (running ? 'NOVA is working…' : 'Latest task updates')}
                      </span>
                    </span>
                    <span className={`activity-chevron ${activityExpanded ? 'open' : ''}`} aria-hidden="true">⌄</span>
                  </button>

                  {activityExpanded && (
                    <div className="activity-details" id="nova-activity-details">
                      {statusMessage && (
                        <p className="activity-current-status">{statusMessage}</p>
                      )}
                      {curatedEvents.length > 0 ? (
                        <div className="activity-event-list">
                          {curatedEvents.map((event) => (
                            <div className="activity-event" key={event.id}>
                              <span className="activity-event-icon" aria-hidden="true">{event.icon || '✨'}</span>
                              <span>{event.message}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="activity-empty">Progress updates will appear here while NOVA works.</p>
                      )}
                    </div>
                  )}
                </section>
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
                <button
                  className={`microphone ${listening ? 'voice-listening' : ''}`}
                  aria-label={listening ? 'Stop voice input' : 'Start voice input'}
                  title={listening ? 'Stop listening' : 'Speak a command'}
                  aria-pressed={listening}
                  type="button"
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    toggleVoiceInput()
                  }}
                >
                  {listening ? (
                    <span className="voice-wave" aria-hidden="true">
                      <i /><i /><i /><i /><i />
                    </span>
                  ) : <MicIcon />}
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