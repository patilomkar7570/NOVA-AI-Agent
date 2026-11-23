import { useState } from 'react'

export default function ProductShowcase({ onLaunchChat, onSelectMode }) {
  const [activeStage, setActiveStage] = useState(0)

  const stages = [
    {
      step: '01',
      title: 'Understands Intent',
      badge: 'Natural Comprehension',
      desc: 'NOVA decodes natural language, spoken voice, screenshots, or attached documents. It contextualizes user goals without requiring rigid prompts.',
      icon: '🧠',
      details: [
        'Multi-modal prompt interpretation (voice, text, image, code)',
        'Automatic task classification & domain detection',
        'Cross-session memory injection for personalized context',
      ],
      previewSnippet: {
        type: 'prompt',
        user: 'Research the latest quarterly GPU benchmark figures, generate a comparison table, and save it to my Documents folder.',
      },
    },
    {
      step: '02',
      title: 'Plans the Task',
      badge: 'Dynamic Graph Planning',
      desc: 'Instead of linear guessing, NOVA synthesizes a multi-step execution plan with verification checkpoints and approval safeguards.',
      icon: '🗺️',
      details: [
        'Dynamic directed acyclic graph (DAG) step planning',
        'Human-in-the-loop review mode for critical operations',
        'Self-healing step retries upon encountering unexpected web UI shifts',
      ],
      previewSnippet: {
        type: 'plan',
        steps: [
          'Step 1: Open Brave and search AnandTech & Tom\'s Hardware',
          'Step 2: Scrape benchmark data tables using browser agent',
          'Step 3: Coder agent synthesizes structured comparison table',
          'Step 4: Desktop agent verifies and saves file to Documents/Benchmarks.csv',
        ],
      },
    },
    {
      step: '03',
      title: 'Coordinates Specialists',
      badge: 'Multi-Agent Swarm',
      desc: 'NOVA orchestrates dedicated specialist agents in parallel—Coder, Browser, Desktop, Research, and Reaction agents collaborate concurrently.',
      icon: '⚡',
      details: [
        'Browser Agent: Autonomous web navigation & form automation',
        'Desktop Agent: Windows UI automation & native software control',
        'Coder Agent: Sandboxed Python scripting, calculation & file I/O',
        'Research Agent: In-depth web synthesis and factual citation',
      ],
      previewSnippet: {
        type: 'swarm',
        activeAgents: [
          { name: 'Browser Agent', status: 'Extracting DOM tables', color: '#4A90E2' },
          { name: 'Coder Agent', status: 'Formatting CSV & KaTeX tables', color: '#50E3C2' },
          { name: 'Desktop Agent', status: 'Staging Windows filesystem target', color: '#B8E986' },
        ],
      },
    },
    {
      step: '04',
      title: 'Executes via Tools',
      badge: 'Native & Sandboxed Tools',
      desc: 'Agents interact directly with the local system through verified tool calls, Playwright webview sessions, and Windows accessibility APIs.',
      icon: '🛠️',
      details: [
        'Native Windows application launch & control',
        'Autonomous browser clicks, inputs, scrolls, and downloads',
        'Local Ollama inference with zero cloud latency and total privacy',
      ],
      previewSnippet: {
        type: 'execution',
        tools: [
          { tool: 'browser_action', param: 'navigate("https://benchmarks.hw/gpu")', state: 'Done' },
          { tool: 'write_file', param: 'Path="Documents/gpu_benchmarks.csv"', state: 'Done' },
          { tool: 'local_voice_synth', param: 'Voicebox neural playback', state: 'Streaming' },
        ],
      },
    },
    {
      step: '05',
      title: 'Presents the Result',
      badge: 'Verified Synthesis',
      desc: 'Delivers high-fidelity responses, interactive artifacts, downloadable files, and synchronized voice narration via Voicebox.',
      icon: '✨',
      details: [
        'Streaming markdown typography with KaTeX math rendering',
        'Interactive Generative UI cards and downloadable artifacts',
        'Real-time neural audio playback with Mercury Orb fluidity',
      ],
      previewSnippet: {
        type: 'result',
        summary: 'GPU benchmark synthesis generated: RTX 5090 leads with 134 FPS avg (+42% vs 4090). CSV saved to your Documents folder.',
      },
    },
  ]

  const current = stages[activeStage]

  return (
    <section className="luxury-section product-showcase-section" id="showcase">
      <div className="luxury-section-container">
        {/* Section Header */}
        <div className="luxury-section-header">
          <span className="luxury-section-eyebrow">ARCHITECTURAL STORY</span>
          <h2 className="luxury-section-title">
            How NOVA turns complex intent <br />
            <span className="luxury-gradient-text">into autonomous execution.</span>
          </h2>
          <p className="luxury-section-subtitle">
            An interconnected multi-agent architecture designed to understand, plan, delegate, execute, and deliver verified results without manual intervention.
          </p>
        </div>

        {/* 5-Step Stage Progression Tabs */}
        <div className="showcase-stages-nav" role="tablist" aria-label="Showcase Stages">
          {stages.map((stage, idx) => (
            <button
              key={stage.step}
              type="button"
              role="tab"
              aria-selected={activeStage === idx}
              className={`showcase-stage-pill ${activeStage === idx ? 'is-active' : ''}`}
              onClick={() => setActiveStage(idx)}
            >
              <span className="showcase-stage-num">{stage.step}</span>
              <span className="showcase-stage-label">{stage.title}</span>
            </button>
          ))}
        </div>

        {/* Active Stage Display Panel */}
        <div className="showcase-stage-panel">
          {/* Left Column: Stage Explanation */}
          <div className="showcase-stage-info">
            <div className="showcase-badge-row">
              <span className="showcase-badge-icon">{current.icon}</span>
              <span className="showcase-badge-text">{current.badge}</span>
            </div>
            <h3 className="showcase-stage-heading">
              {current.step}. {current.title}
            </h3>
            <p className="showcase-stage-description">{current.desc}</p>

            <ul className="showcase-details-list">
              {current.details.map((item, i) => (
                <li key={i} className="showcase-detail-item">
                  <span className="showcase-check-icon">✓</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>

            <div className="showcase-action-row">
              <button
                type="button"
                className="showcase-try-step-btn"
                onClick={() => {
                  if (onSelectMode) onSelectMode('auto')
                  if (onLaunchChat) onLaunchChat()
                }}
              >
                <span>Try this stage in Command Chat</span>
                <span className="step-arrow">→</span>
              </button>
            </div>
          </div>

          {/* Right Column: Live Simulated Preview Window */}
          <div className="showcase-stage-preview">
            <div className="preview-window-frame">
              {/* Window Header */}
              <div className="preview-window-header">
                <div className="preview-window-dots">
                  <span className="dot dot-close" />
                  <span className="dot dot-min" />
                  <span className="dot dot-max" />
                </div>
                <div className="preview-window-title">
                  nova-core • {current.title.toLowerCase().replace(/\s+/g, '-')}
                </div>
                <span className="preview-window-tag">LOCAL AGENT</span>
              </div>

              {/* Window Body */}
              <div className="preview-window-body">
                {current.previewSnippet.type === 'prompt' && (
                  <div className="preview-box preview-prompt-box">
                    <div className="preview-role-label">USER INTENT</div>
                    <p className="preview-quote">"{current.previewSnippet.user}"</p>
                    <div className="preview-status-pill">
                      <span className="status-dot green" />
                      Decomposing into executable agent sub-tasks…
                    </div>
                  </div>
                )}

                {current.previewSnippet.type === 'plan' && (
                  <div className="preview-box preview-plan-box">
                    <div className="preview-role-label">EXECUTION PLAN DAG</div>
                    <div className="preview-plan-steps">
                      {current.previewSnippet.steps.map((st, i) => (
                        <div key={i} className="preview-step-row">
                          <span className="preview-step-badge">0{i + 1}</span>
                          <span className="preview-step-text">{st}</span>
                          <span className="preview-step-check">✓</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {current.previewSnippet.type === 'swarm' && (
                  <div className="preview-box preview-swarm-box">
                    <div className="preview-role-label">COORDINATED AGENT SWARM</div>
                    <div className="preview-swarm-cards">
                      {current.previewSnippet.activeAgents.map((ag, i) => (
                        <div key={i} className="preview-agent-card">
                          <div className="preview-agent-head">
                            <span className="agent-indicator" style={{ background: ag.color }} />
                            <strong>{ag.name}</strong>
                          </div>
                          <div className="preview-agent-task">{ag.status}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {current.previewSnippet.type === 'execution' && (
                  <div className="preview-box preview-exec-box">
                    <div className="preview-role-label">SYSTEM TOOL INVOCATIONS</div>
                    <div className="preview-tools-list">
                      {current.previewSnippet.tools.map((tl, i) => (
                        <div key={i} className="preview-tool-item">
                          <code>{tl.tool}</code>
                          <span className="preview-tool-param">{tl.param}</span>
                          <span className="preview-tool-badge">{tl.state}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {current.previewSnippet.type === 'result' && (
                  <div className="preview-box preview-result-box">
                    <div className="preview-role-label">VERIFIED SYNTHESIS</div>
                    <div className="preview-result-bubble">
                      <p>{current.previewSnippet.summary}</p>
                    </div>
                    <div className="preview-artifact-chip">
                      <span className="artifact-icon">📄</span>
                      <span className="artifact-title">gpu_benchmarks.csv</span>
                      <span className="artifact-size">18.4 KB • Saved to Documents</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
