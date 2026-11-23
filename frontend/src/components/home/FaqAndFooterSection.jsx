import { useState } from 'react'

const FAQ_ITEMS = [
  {
    q: 'What is NOVA AI Agent and how is it different from conventional chat models?',
    a: 'Unlike traditional LLM chatbots that merely generate text responses, NOVA is a full-fledged autonomous operating system agent. It can read and write files, navigate web applications using a real headless Chromium engine, orchestrate multi-step code refactoring, verify outcomes with local test suites, and execute voice dialogues—all anchored directly on your machine.'
  },
  {
    q: 'Does NOVA require an active internet connection to execute local tasks?',
    a: 'No. When paired with local Ollama models (such as Qwen 2.5, Llama 3.3, or Mistral) and the local VoiceBox acoustic engine, NOVA functions completely offline. File manipulation, multi-agent planning, and system automation execute entirely on your local hardware.'
  },
  {
    q: 'How does the multi-agent architecture work under the hood?',
    a: 'When you submit a goal, NOVA does not immediately jump into ad-hoc tool execution. Instead, a designated Planner synthesizes a directed acyclic graph (DAG) of discrete milestones. Specialist subagents (e.g. Browser Specialist, Terminal Runner, Code Inspector) are dispatched to execute parallel nodes, and a Verifier audits the outcome before presenting the completed result.'
  },
  {
    q: 'Is my private codebase, sensitive files, or telemetry sent to third-party cloud servers?',
    a: 'Never. NOVA is engineered with sovereign privacy as a core tenet. There is zero telemetry tracking, zero usage analytics uploading, and zero forced cloud sync. Your data, embeddings, chat history, and memory stay exclusively on your local storage.'
  },
  {
    q: 'What LLM backends and providers does NOVA support?',
    a: 'NOVA natively supports local inference via Ollama, LM Studio, and llama.cpp, alongside optional cloud providers including Google Gemini, Anthropic Claude, and OpenAI via user-supplied API keys stored in your local encrypted vault.'
  },
  {
    q: 'How does real-time duplex Voice Mode and VoiceBox operate?',
    a: 'Voice Mode leverages low-latency audio capture with WebAudio, local Whisper or fast speech-to-text models, and the VoiceBox acoustic synthesizer. The real-time Mercury Orb acts as a fluid visualizer, dynamically reflecting speaker pitch, amplitude, and neural response state.'
  },
  {
    q: 'Can NOVA safely interact with my Windows desktop and file system?',
    a: 'Yes. NOVA operates within a strict sandboxed permission model. Every destructive or external action—such as executing arbitrary shell commands, modifying critical directories, or accessing external networks—triggers a granular human confirmation dialog unless explicitly marked safe by you.'
  },
  {
    q: 'How do I contribute, extend plugins, or develop custom subagents?',
    a: 'NOVA provides an extensible plugin and subagent API. You can define custom subagents with specialized system prompts and tool manifests in Python or JavaScript. Visit our GitHub repository and official documentation to view developer guides and sample extensions.'
  }
]

export default function FaqAndFooterSection({ onNavigate, onLaunchVoice, onLaunchChat }) {
  const [openIdx, setOpenIdx] = useState(null)

  const toggleFaq = (idx) => {
    setOpenIdx((prev) => (prev === idx ? null : idx))
  }

  return (
    <>
      <section className="luxury-section faq-section" id="faq">
        <div className="luxury-section-header">
          <div className="luxury-section-badge">
            <span className="badge-pulse" />
            FREQUENTLY ASKED QUESTIONS
          </div>
          <h2 className="luxury-section-title">
            Inquiries & Technical Clarifications
          </h2>
          <p className="luxury-section-subtitle">
            Everything you need to know about NOVA's sovereign runtime, multi-agent coordination, and local security.
          </p>
        </div>

        <div className="faq-accordion">
          {FAQ_ITEMS.map((item, idx) => {
            const isOpen = openIdx === idx
            return (
              <div
                key={idx}
                className={`faq-item ${isOpen ? 'is-open' : ''}`}
              >
                <button
                  type="button"
                  className="faq-question-btn"
                  onClick={() => toggleFaq(idx)}
                  aria-expanded={isOpen}
                >
                  <span className="faq-question-text">{item.q}</span>
                  <span className="faq-toggle-icon">
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      {isOpen ? (
                        <line x1="5" y1="12" x2="19" y2="12" />
                      ) : (
                        <>
                          <line x1="12" y1="5" x2="12" y2="19" />
                          <line x1="5" y1="12" x2="19" y2="12" />
                        </>
                      )}
                    </svg>
                  </span>
                </button>

                {isOpen && (
                  <div className="faq-answer-pane">
                    <p className="faq-answer-text">{item.a}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* Luxury Footer */}
      <footer className="luxury-footer">
        <div className="luxury-footer-ambient" />

        <div className="luxury-footer-content">
          <div className="footer-top-row">
            <div className="footer-brand-col">
              <div className="footer-brand-lockup">
                <img
                  src="/nova-logo.png"
                  alt="NOVA"
                  className="footer-logo-img"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
                <span className="footer-brand-name">NOVA</span>
                <span className="footer-brand-badge">Beta 0.6</span>
              </div>
              <p className="footer-brand-tagline">
                The local-first autonomous intelligence platform. Privacy-native, multi-agent architecture designed for high-performance human computing.
              </p>
            </div>

            <div className="footer-links-grid">
              <div className="footer-col">
                <span className="footer-col-title">Product</span>
                <button type="button" className="footer-link-btn" onClick={() => onNavigate('overview')}>Overview</button>
                <button type="button" className="footer-link-btn" onClick={() => onNavigate('capabilities')}>Capabilities</button>
                <button type="button" className="footer-link-btn" onClick={() => onNavigate('architecture')}>Architecture</button>
                <button type="button" className="footer-link-btn" onClick={() => onNavigate('specs')}>System Specs</button>
                <button type="button" className="footer-link-btn" onClick={() => onNavigate('how-it-works')}>Workflow</button>
                <button type="button" className="footer-link-btn" onClick={() => onNavigate('use-cases')}>Use Cases</button>
                <button type="button" className="footer-link-btn" onClick={() => onNavigate('download')}>Download Beta 0.6</button>
              </div>

              <div className="footer-col">
                <span className="footer-col-title">Interfaces</span>
                <button type="button" className="footer-link-btn" onClick={onLaunchChat}>Command Chat</button>
                <button type="button" className="footer-link-btn" onClick={onLaunchVoice}>Voice Mode</button>
                <button type="button" className="footer-link-btn" onClick={() => onNavigate('faq')}>FAQ</button>
                <a
                  href="https://github.com/patilomkar7570/NOVA-AI-Agent"
                  target="_blank"
                  rel="noreferrer"
                  className="footer-link"
                >
                  GitHub Source
                </a>
              </div>

              <div className="footer-col">
                <span className="footer-col-title">Sovereignty & Trust</span>
                <span className="footer-static-item">Zero Telemetry Beacons</span>
                <span className="footer-static-item">Local Ollama Runtime</span>
                <span className="footer-static-item">Voicebox Speech Loop</span>
                <span className="footer-static-item">Approval-Gated Sandbox</span>
              </div>
            </div>
          </div>

          <div className="footer-bottom-row">
            <span className="footer-copy">
              &copy; {new Date().getFullYear()} NOVA Platform • Beta 0.6. Sovereign local-first computing for Windows.
            </span>
            <div className="footer-bottom-links">
              <span className="footer-status-pill">
                <span className="status-live-dot" />
                Beta 0.6 • Local Host Active
              </span>
            </div>
          </div>
        </div>
      </footer>
    </>
  )
}
