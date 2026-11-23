export default function DownloadSection({ onLaunchChat }) {
  return (
    <section className="luxury-section download-section" id="download">
      <div className="download-card">
        <div className="download-ambient-glow" />

        <div className="download-content">
          <div className="download-badge">
            <span className="badge-pulse" />
            EARLY ACCESS • BETA 0.6 (v0.6.0-beta)
          </div>

          <h2 className="download-title">
            Get started with NOVA Beta 0.6
          </h2>

          <p className="download-desc">
            Experience sovereign, local-first artificial intelligence on Windows. Zero cloud lock-in, zero telemetry,
            and immediate access to desktop control, local Ollama models, Voicebox speech dialogue, and autonomous web & OS automation.
          </p>

          <div className="download-ctas">
            <a
              href="https://github.com/patilomkar7570/NOVA-AI-Agent/releases"
              target="_blank"
              rel="noreferrer"
              className="luxury-download-primary"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <span>Download Beta 0.6 Release</span>
              <span className="cta-meta">Source Archive • GitHub</span>
            </a>

            <button
              type="button"
              className="luxury-download-secondary"
              onClick={onLaunchChat}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              <span>Launch Command Chat</span>
            </button>
          </div>

          {/* Honest Beta Status Note */}
          <div className="download-alpha-note">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="alpha-note-icon">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <span>
              <strong>Deployment Status:</strong> Beta 0.6 introduces native Desktop Control and Coder Agent specialists alongside autonomous browser control. Launch immediately via <code>Startup-Portable.bat</code>.
            </span>
          </div>

          <div className="download-specs-grid">
            <div className="spec-item">
              <span className="spec-label">Platform</span>
              <span className="spec-val">Windows 10 / 11 (x64)</span>
            </div>
            <div className="spec-item">
              <span className="spec-label">Memory</span>
              <span className="spec-val">16 GB RAM (32 GB Recommended)</span>
            </div>
            <div className="spec-item">
              <span className="spec-label">Runtimes</span>
              <span className="spec-val">Python 3.10+ & Node.js 18+</span>
            </div>
            <div className="spec-item">
              <span className="spec-label">Licensing</span>
              <span className="spec-val">Open Sovereign Architecture</span>
            </div>
          </div>

          <div className="download-links-row">
            <a
              href="https://github.com/patilomkar7570/NOVA-AI-Agent"
              target="_blank"
              rel="noreferrer"
              className="sub-link"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
              </svg>
              GitHub Repository
            </a>
            <span className="link-divider">•</span>
            <a
              href="https://github.com/patilomkar7570/NOVA-AI-Agent/blob/main/README.md"
              target="_blank"
              rel="noreferrer"
              className="sub-link"
            >
              Installation Guide
            </a>
            <span className="link-divider">•</span>
            <a
              href="https://github.com/patilomkar7570/NOVA-AI-Agent/releases"
              target="_blank"
              rel="noreferrer"
              className="sub-link"
            >
              Release Notes (v0.6.0-beta)
            </a>
          </div>
        </div>
      </div>
    </section>
  )
}
