import { useState } from 'react'

const USE_CASES = [
  {
    id: 'engineering',
    category: 'Software Engineering',
    title: 'Autonomous Codebase Refactoring & Test Verification',
    description:
      'NOVA inspects entire repositories, maps dependency trees, drafts multi-file refactors, runs local unit test suites, and verifies zero regression before committing.',
    metrics: ['185/185 Tests Verified', 'Zero Cloud Leak', 'Instant Rollback'],
    quote: '"NOVA diagnosed our race condition in seconds and verified the solution against the entire test harness."'
  },
  {
    id: 'research',
    category: 'Intelligence & Research',
    title: 'Deep Multi-Source Web Synthesis & Structured Reporting',
    description:
      'Send NOVA to inspect competitor benchmarks, scrape live API specs via Chromium, parse PDF papers, and compile synthesized Markdown artifacts with interactive charts.',
    metrics: ['Live DOM Traversal', 'Markdown Artifacts', 'Citations Included'],
    quote: '"Turned 4 hours of tedious documentation reading into a crisp, verifiable architectural dossier."'
  },
  {
    id: 'system',
    category: 'OS & Workspace Automation',
    title: 'Sovereign Operating System Management',
    description:
      'Organize disorganized download folders, extract text from screenshots, run batch ffmpeg transcodings, and configure developer environment variables with explicit approval safeguards.',
    metrics: ['Human Authorization Gate', 'Native Windows & Shell', 'Safe Dry-Run'],
    quote: '"Safely handled thousands of files across deep directory hierarchies without risking system stability."'
  },
  {
    id: 'voice',
    category: 'Ambient Voice Work',
    title: 'Hands-Free Pair Programming & Voice Memos',
    description:
      'Use the duplex Voice Mode and reactive Mercury Orb while cooking, typing, or pacing around the room. Discuss architecture, dictate thoughts, and hear natural, warm spoken responses.',
    metrics: ['VoiceBox Acoustic Engine', 'Audio Reactive Shader', '<150ms Latency'],
    quote: '"Feels like collaborating with a thoughtful senior architect who listens and speaks in real time."'
  }
]

export default function UseCasesSection() {
  const [activeTab, setActiveTab] = useState(0)

  return (
    <section className="luxury-section use-cases-section" id="use-cases">
      <div className="luxury-section-header">
        <div className="luxury-section-badge">
          <span className="badge-pulse" />
          APPLIED INTELLIGENCE
        </div>
        <h2 className="luxury-section-title">
          Engineered for high-stakes professional workflows.
        </h2>
        <p className="luxury-section-subtitle">
          From full-stack development to autonomous web reconnaissance, discover how NOVA accelerates daily cognitive labor.
        </p>
      </div>

      <div className="use-cases-tabs">
        {USE_CASES.map((uc, idx) => (
          <button
            key={uc.id}
            type="button"
            className={`use-case-tab-btn ${activeTab === idx ? 'is-active' : ''}`}
            onClick={() => setActiveTab(idx)}
          >
            {uc.category}
          </button>
        ))}
      </div>

      <div className="use-case-hero-card">
        <div className="use-case-left">
          <span className="use-case-eyebrow">{USE_CASES[activeTab].category}</span>
          <h3 className="use-case-headline">{USE_CASES[activeTab].title}</h3>
          <p className="use-case-body">{USE_CASES[activeTab].description}</p>

          <div className="use-case-metrics">
            {USE_CASES[activeTab].metrics.map((m, i) => (
              <div key={i} className="metric-pill">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>{m}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="use-case-right">
          <div className="use-case-quote-card">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="quote-icon">
              <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z" />
              <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z" />
            </svg>
            <p className="quote-text">{USE_CASES[activeTab].quote}</p>
            <div className="quote-author">
              <div className="author-avatar" />
              <div className="author-info">
                <span className="author-name">Verified Developer</span>
                <span className="author-role">NOVA Early Access Pioneer</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
