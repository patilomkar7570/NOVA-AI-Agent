import { useState, useEffect } from 'react'

export default function LuxuryHeader({
  darkMode,
  setThemeMode,
  selectedAccent,
  onOpenVoiceMode,
  onOpenSettings,
  onNewChat,
  backendOnline,
}) {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const navItems = [
    { label: 'Overview', href: '#overview' },
    { label: 'Capabilities', href: '#capabilities' },
    { label: 'Architecture', href: '#architecture' },
    { label: 'Specs', href: '#specs' },
    { label: 'Workflow', href: '#how-it-works' },
    { label: 'Use Cases', href: '#use-cases' },
    { label: 'FAQ', href: '#faq' },
    { label: 'Download', href: '#download' },
  ]

  const handleNavClick = (e, href) => {
    e.preventDefault()
    setMobileOpen(false)
    const el = document.querySelector(href)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const toggleTheme = () => {
    setThemeMode((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  return (
    <header className={`luxury-nav-shell ${scrolled ? 'is-scrolled' : ''}`}>
      <div className="luxury-nav-inner">
        {/* Brand Logo & Title */}
        <a href="#overview" className="luxury-nav-brand" onClick={(e) => handleNavClick(e, '#overview')} aria-label="NOVA Home">
          <div className="luxury-brand-mark">
            <img src="/nova-logo.png" alt="NOVA Brand Logo" className="luxury-brand-logo-img" />
          </div>
          <div className="luxury-brand-text">
            <span className="luxury-brand-name">NOVA</span>
            <span className="luxury-brand-pill">AI AGENT</span>
          </div>
        </a>

        {/* Center Desktop Navigation */}
        <nav className="luxury-nav-links" aria-label="Main Navigation">
          {navItems.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className="luxury-nav-link"
              onClick={(e) => handleNavClick(e, item.href)}
            >
              {item.label}
            </a>
          ))}
        </nav>

        {/* Right Action Island */}
        <div className="luxury-nav-actions">
          {/* Engine Status Dot */}
          <div
            className={`luxury-engine-status ${backendOnline ? 'is-online' : 'is-offline'}`}
            title={backendOnline ? 'NOVA Local Agent Engine: Operational' : 'NOVA Backend: Offline'}
            aria-label="Engine Status"
          >
            <span className="luxury-status-pulse" />
            <span className="luxury-status-label">{backendOnline ? 'Local Engine' : 'Offline'}</span>
          </div>

          {/* Theme Switcher Button */}
          <button
            type="button"
            className="luxury-icon-btn theme-toggle-btn"
            onClick={toggleTheme}
            aria-label={`Switch to ${darkMode ? 'light' : 'dark'} mode`}
            title={`Switch to ${darkMode ? 'Light' : 'Dark'} theme`}
          >
            {darkMode ? (
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="5" />
                <line x1="12" y1="1" x2="12" y2="3" />
                <line x1="12" y1="21" x2="12" y2="23" />
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                <line x1="1" y1="12" x2="3" y2="12" />
                <line x1="21" y1="12" x2="23" y2="12" />
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
              </svg>
            ) : (
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>

          {/* Settings / Accent Trigger */}
          <button
            type="button"
            className="luxury-icon-btn palette-btn"
            onClick={onOpenSettings}
            aria-label="Palette and Settings"
            title={`Theme: ${selectedAccent?.name || 'Default'}`}
          >
            <span
              className="luxury-accent-dot"
              style={{
                background: darkMode && selectedAccent?.darkPrimary ? selectedAccent.darkPrimary : selectedAccent?.primary,
              }}
            />
          </button>

          {/* Voice Mode Launcher */}
          <button
            type="button"
            className="luxury-voice-pill"
            onClick={onOpenVoiceMode}
            aria-label="Open Voice Mode"
            title="Launch Fullscreen Voice Mode"
          >
            <span className="luxury-voice-orb-mini" />
            <span className="luxury-voice-label">Voice Mode</span>
          </button>

          {/* New Chat Primary Action */}
          <button
            type="button"
            className="luxury-chat-btn"
            onClick={onNewChat}
            aria-label="Start New Chat Session"
          >
            <span>New Chat</span>
            <span className="luxury-btn-arrow">→</span>
          </button>

          {/* Mobile Hamburger Toggle */}
          <button
            type="button"
            className="luxury-mobile-toggle"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label={mobileOpen ? 'Close Navigation Menu' : 'Open Navigation Menu'}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? '✕' : '☰'}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileOpen && (
        <div className="luxury-mobile-drawer" role="dialog" aria-modal="true">
          <div className="luxury-mobile-drawer-links">
            {navItems.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="luxury-mobile-link"
                onClick={(e) => handleNavClick(e, item.href)}
              >
                {item.label}
              </a>
            ))}
          </div>
          <div className="luxury-mobile-drawer-footer">
            <button type="button" className="luxury-mobile-voice-btn" onClick={() => { setMobileOpen(false); onOpenVoiceMode(); }}>
              Open Voice Mode
            </button>
            <button type="button" className="luxury-mobile-chat-btn" onClick={() => { setMobileOpen(false); onNewChat(); }}>
              Start New Chat Session
            </button>
          </div>
        </div>
      )}
    </header>
  )
}
