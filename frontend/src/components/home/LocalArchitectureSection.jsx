import { useState } from 'react'

const ARCH_NODES = [
  {
    id: 'frontend',
    title: 'NOVA Workstation UI',
    category: 'CLIENT INTERFACE',
    status: 'Localhost:5173',
    role: 'Responsive React 19 application running locally. Renders the command bar, agent status HUD, real-time response streams, and WebAudio Mercury Orb.',
    tech: ['React 19', 'Vite', 'WebAudio API', 'HTML5 Canvas'],
    security: 'Sandboxed inside your browser. No external telemetry or remote usage beacons.'
  },
  {
    id: 'backend',
    title: 'NOVA Cognitive Core',
    category: 'PYTHON BACKEND',
    status: '127.0.0.1:8000',
    role: 'FastAPI agent coordinator and task planner. Decomposes user intent into DAG execution graphs, orchestrates subagents, and enforces confirmation gates.',
    tech: ['Python 3.14 / 3.10+', 'FastAPI', 'SQLite Vault', 'Subprocess Sandbox'],
    security: 'Strict authorization barrier. Potentially destructive shell commands require explicit approval.'
  },
  {
    id: 'ollama',
    title: 'Ollama Neural Engine',
    category: 'LOCAL LLM RUNTIME',
    status: 'Localhost:11434',
    role: 'Direct GPU/CPU inference engine. Runs Qwen 2.5, Llama 3.3, Mistral, and DeepSeek locally on your hardware with streaming token generation.',
    tech: ['Ollama Runtime', 'CUDA / DirectML', 'GGUF Quantization', 'Zero Token Fees'],
    security: '100% private. Prompt context and embeddings never traverse outside your device.'
  },
  {
    id: 'voicebox',
    title: 'Voicebox Acoustic Engine',
    category: 'SPEECH INFRASTRUCTURE',
    status: 'Native Python Module',
    role: 'Local speech synthesis and transcription. Powered by Whisper STT and customizable Voicebox audio profiles for fluid vocal dialogue.',
    tech: ['Voicebox Synthesizer', 'Whisper STT', 'Multi-Profile Audio', 'Sub-150ms Loop'],
    security: 'Processes audio locally. Fallback browser speech recognition uses platform services.'
  },
  {
    id: 'browser',
    title: 'Chromium Worker',
    category: 'WEB AUTOMATION',
    status: 'Playwright Managed',
    role: 'Autonomous web agent navigating live websites, extracting DOM trees, analyzing screenshots, and researching external web information.',
    tech: ['Playwright', 'Headless & Visual Chromium', 'Brave / Edge', 'Anti-bot Respectful'],
    security: 'Requires active internet. Operates in isolated session storage without accessing host cookies.'
  }
]

export default function LocalArchitectureSection() {
  const [selectedNode, setSelectedNode] = useState('backend')

  const activeNode = ARCH_NODES.find((n) => n.id === selectedNode) || ARCH_NODES[1]

  return (
    <section className="luxury-section local-arch-section" id="architecture">
      <div className="luxury-section-header">
        <div className="luxury-section-badge">
          <span className="badge-pulse" />
          SOVEREIGN LOCAL-FIRST COMPUTING
        </div>
        <h2 className="luxury-section-title">
          Your machine. Your models. Absolute user control.
        </h2>
        <p className="luxury-section-subtitle">
          NOVA replaces opaque cloud subscription lock-in with an observable, local-first computing topology.
          Inspect every process boundary, data flow, and permission checkpoint below.
        </p>
      </div>

      <div className="local-arch-container">
        {/* Architecture Topology Map */}
        <div className="arch-topology-canvas">
          <div className="arch-topology-titlebar">
            <span className="arch-titlebar-dot" />
            <span className="arch-titlebar-label">NOVA System Topology & Boundary Map</span>
            <span className="arch-titlebar-meta">Beta 0.6 Architecture</span>
          </div>

          <div className="arch-nodes-grid">
            {ARCH_NODES.map((node) => {
              const isSelected = selectedNode === node.id
              return (
                <button
                  key={node.id}
                  type="button"
                  className={`arch-node-card ${isSelected ? 'is-selected' : ''}`}
                  onClick={() => setSelectedNode(node.id)}
                >
                  <div className="arch-node-header">
                    <span className="arch-node-category">{node.category}</span>
                    <span className="arch-node-status-pill">{node.status}</span>
                  </div>
                  <h3 className="arch-node-name">{node.title}</h3>
                  <div className="arch-node-pills">
                    {node.tech.slice(0, 2).map((t, idx) => (
                      <span key={idx} className="arch-mini-pill">{t}</span>
                    ))}
                  </div>
                </button>
              )
            })}
          </div>

          {/* Connectors Visual Line */}
          <div className="arch-flow-indicator">
            <div className="flow-path-line" />
            <span className="flow-badge">High-Speed IPC & Local Loopback (Zero External Telemetry)</span>
          </div>
        </div>

        {/* Selected Node Inspector Pane */}
        <div className="arch-inspector-card">
          <div className="inspector-badge-row">
            <span className="inspector-cat">{activeNode.category}</span>
            <span className="inspector-status-badge">● {activeNode.status}</span>
          </div>

          <h3 className="inspector-node-title">{activeNode.title}</h3>
          <p className="inspector-node-role">{activeNode.role}</p>

          <div className="inspector-spec-block">
            <span className="spec-block-title">Core Technology Stack</span>
            <div className="inspector-tech-tags">
              {activeNode.tech.map((t, idx) => (
                <span key={idx} className="tech-badge">{t}</span>
              ))}
            </div>
          </div>

          <div className="inspector-security-block">
            <div className="security-icon-row">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <span className="security-title">Security & Permission Invariant</span>
            </div>
            <p className="security-desc">{activeNode.security}</p>
          </div>
        </div>
      </div>

      {/* Honest Principles Grid */}
      <div className="arch-principles-grid">
        <div className="principle-card">
          <div className="principle-icon-wrap">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="4" y="4" width="16" height="16" rx="2" />
              <rect x="9" y="9" width="6" height="6" />
            </svg>
          </div>
          <h4>Local Model Independence</h4>
          <p>
            Language models run entirely in your GPU VRAM or system RAM via Ollama. No token pricing tiers,
            no rate-limiting timeouts, and no remote corporate surveillance of your thoughts.
          </p>
        </div>

        <div className="principle-card">
          <div className="principle-icon-wrap">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h4>Granular Human Confirmation</h4>
          <p>
            When a task requires modifying files, installing dependencies, or running shell commands,
            NOVA halts and displays an explicit approval gate with dry-run diffs before execution.
          </p>
        </div>

        <div className="principle-card">
          <div className="principle-icon-wrap">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
            </svg>
          </div>
          <h4>Transparent Web Boundaries</h4>
          <p>
            Local tasks execute completely offline. Whenever research or browser navigation requires the internet,
            NOVA explicitly notes external requests and handles sessions inside sandboxed Chromium contexts.
          </p>
        </div>
      </div>
    </section>
  )
}
