import { useState } from 'react'

const CAPABILITIES = [
  {
    id: 'orchestration',
    tag: 'Autonomous Multi-Agent',
    title: 'Autonomous Multi-Agent Orchestration',
    description:
      'NOVA decomposes intricate human objectives into formal execution plans. A dedicated planner, specialist executors, and verification agents cooperate in real time to guarantee verified outcomes.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
    highlights: ['Plan DAGs with checkpoint rollbacks', 'Autonomous specialist routing', 'Parallelized tool invocation'],
    span: 'col-span-2'
  },
  {
    id: 'browser',
    tag: 'Chromium Engine',
    title: 'Autonomous Browser Exploration',
    description:
      'Direct Playwright-driven Chromium runtime navigating modern single-page apps, inspecting visual elements, evaluating DOM trees, and gathering intelligence without brittle APIs.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    ),
    highlights: ['Full headless & visual execution', 'Dynamic screenshot inspection', 'Anti-bot respectful navigation'],
    span: 'col-span-1'
  },
  {
    id: 'ollama',
    tag: 'Local Intelligence',
    title: 'Zero-Cloud Local Neural Engine',
    description:
      'Native Ollama and local LLM integration. Run Qwen 2.5, Llama 3.3, Mistral, and DeepSeek directly on your GPU or CPU without internet dependency or token subscription metering.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <rect x="9" y="9" width="6" height="6" />
        <line x1="9" y1="1" x2="9" y2="4" />
        <line x1="15" y1="1" x2="15" y2="4" />
        <line x1="9" y1="20" x2="9" y2="23" />
        <line x1="15" y1="20" x2="15" y2="23" />
        <line x1="20" y1="9" x2="23" y2="9" />
        <line x1="20" y1="14" x2="23" y2="14" />
        <line x1="1" y1="9" x2="4" y2="9" />
        <line x1="1" y1="14" x2="4" y2="14" />
      </svg>
    ),
    highlights: ['VRAM auto-allocation', 'Streaming token generation', 'Zero external API dependence'],
    span: 'col-span-1'
  },
  {
    id: 'voice',
    tag: 'Audio Interface',
    title: 'Duplex Voice Mode & Mercury Orb',
    description:
      'Natural, zero-latency duplex vocal communication powered by VoiceBox and WebAudio. The fluid Mercury Orb reacts dynamically to your pitch, amplitude, and neural response states.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
    ),
    highlights: ['Sub-150ms acoustic response', 'Audio-reactive organic shader', 'Hands-free ambient execution'],
    span: 'col-span-2'
  },
  {
    id: 'memory',
    tag: 'Context Retention',
    title: 'Persistent Memory & Workspace Graph',
    description:
      'Long-term relational recall tracks your habits, previous codebase structures, user preferences, and working conventions across weeks of asynchronous multi-tasking.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    ),
    highlights: ['Vector search across project files', 'Cross-session continuity', 'Autonomous preference refinement'],
    span: 'col-span-1'
  },
  {
    id: 'privacy',
    tag: 'Sovereign Security',
    title: 'Cryptographic Privacy & Sandboxing',
    description:
      'Your workspace remains entirely on your machine. Every system command executes in a sandboxed, observable process tree with granular human-in-the-loop authorization gates.',
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
    highlights: ['Zero telemetry or telemetry tracking', 'Granular approval modals for disk/net', 'Local SQLite & secure storage'],
    span: 'col-span-2'
  }
]

export default function CapabilitiesSection() {
  const [activePanel, setActivePanel] = useState(null)

  return (
    <section className="luxury-section capabilities-section" id="capabilities">
      <div className="luxury-section-header">
        <div className="luxury-section-badge">
          <span className="badge-pulse" />
          CORE CAPABILITIES
        </div>
        <h2 className="luxury-section-title">
          Architected for total computational mastery.
        </h2>
        <p className="luxury-section-subtitle">
          NOVA operates as a unified cognitive layer above your operating system, harmonizing local neural models,
          autonomous browsing, multi-agent task planning, and instant acoustic dialogue.
        </p>
      </div>

      <div className="capabilities-grid">
        {CAPABILITIES.map((cap) => (
          <div
            key={cap.id}
            className={`capability-card ${cap.span} ${activePanel === cap.id ? 'is-expanded' : ''}`}
            onMouseEnter={() => setActivePanel(cap.id)}
            onMouseLeave={() => setActivePanel(null)}
          >
            <div className="capability-card-bg-glow" />
            <div className="capability-card-header">
              <div className="capability-icon-wrap">
                {cap.icon}
              </div>
              <span className="capability-tag">{cap.tag}</span>
            </div>

            <h3 className="capability-title">{cap.title}</h3>
            <p className="capability-description">{cap.description}</p>

            <ul className="capability-highlights">
              {cap.highlights.map((item, idx) => (
                <li key={idx} className="capability-highlight-item">
                  <span className="highlight-bullet" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>

            <div className="capability-card-footer">
              <span className="capability-learn-more">
                Explore architectural specification
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
