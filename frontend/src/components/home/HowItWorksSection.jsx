import { useState } from 'react'

const STEPS = [
  {
    step: '01',
    phase: 'INTAKE',
    title: 'Natural Intent Comprehension',
    subtitle: 'From unstructured thought to structured computational goal',
    description:
      'Whether through conversational voice or rapid prompt input, NOVA extracts implicit dependencies, environment contexts, and safety constraints without requiring rigid syntax.',
    codeSnippet: 'User: "Analyze recent commit history, verify test suites, and draft release notes."\n→ Target: [Git, TestRunner, ReleaseDrafter]\n→ Risk Assessment: Read-only + Draft generation (Safe)',
    badge: 'Cognitive Parser'
  },
  {
    step: '02',
    phase: 'SYNTHESIS',
    title: 'Directed Acyclic Plan Generation',
    subtitle: 'Deterministic milestones with automated rollback points',
    description:
      'The cognitive planner constructs a rigorous topological graph of execution steps. Each phase defines clear entry criteria, failure thresholds, and recovery branches before any tool runs.',
    codeSnippet: 'DAG: [FetchLogs] → [RunUnitTests (185)] ─┐\n                        ↓                  ├─→ [CompileNotes]\n                 [LintAudit (0 errors)] ─┘',
    badge: 'Plan Synthesis'
  },
  {
    step: '03',
    phase: 'EXECUTION',
    title: 'Parallel Specialist Dispatch',
    subtitle: 'Sandboxed browser, filesystem, terminal, and LLM workers',
    description:
      'Subagents specialize by task domain: the Chromium Browser navigates live pages, the Terminal Runner invokes local toolchains, and the Code Inspector performs surgical AST edits.',
    codeSnippet: 'Worker 1 (Browser): Chromium navigated localhost:5173 (200 OK)\nWorker 2 (Terminal): npm run build finished in 312ms\nWorker 3 (Analyzer): 0 security flaws detected',
    badge: 'Autonomous Swarm'
  },
  {
    step: '04',
    phase: 'VERIFICATION',
    title: 'Multi-Modal Outcome Audit',
    subtitle: 'Defensive validation before human presentation',
    description:
      'NOVA never assumes success without mathematical proof. Every output, artifact, and diff is inspected against the original human intent before rendering interactive results.',
    codeSnippet: 'Verification: 185/185 unit tests passed (100%)\nArtifact generated: release_v0.3.2.md\nStatus: Complete & Verified • Presentation ready',
    badge: 'Formal Verifier'
  }
]

export default function HowItWorksSection() {
  const [selectedStep, setSelectedStep] = useState(0)

  return (
    <section className="luxury-section how-it-works-section" id="how-it-works">
      <div className="luxury-section-header">
        <div className="luxury-section-badge">
          <span className="badge-pulse" />
          ARCHITECTURE & WORKFLOW
        </div>
        <h2 className="luxury-section-title">
          How NOVA executes with absolute precision.
        </h2>
        <p className="luxury-section-subtitle">
          A four-tier cognitive pipeline turns ambiguous human intent into deterministic, self-verifying computer actions.
        </p>
      </div>

      <div className="how-it-works-container">
        {/* Step Navigation Pill Flow */}
        <div className="how-steps-timeline">
          {STEPS.map((step, idx) => (
            <button
              key={step.step}
              type="button"
              className={`timeline-step-btn ${selectedStep === idx ? 'is-active' : ''}`}
              onClick={() => setSelectedStep(idx)}
            >
              <span className="step-num">{step.step}</span>
              <div className="step-meta">
                <span className="step-phase">{step.phase}</span>
                <span className="step-label">{step.title}</span>
              </div>
            </button>
          ))}
        </div>

        {/* Selected Step Display Card */}
        <div className="step-display-card">
          <div className="step-card-left">
            <div className="step-card-badge">
              <span>Step {STEPS[selectedStep].step}</span>
              <span className="badge-sep">•</span>
              <span>{STEPS[selectedStep].badge}</span>
            </div>
            <h3 className="step-card-title">{STEPS[selectedStep].title}</h3>
            <h4 className="step-card-subtitle">{STEPS[selectedStep].subtitle}</h4>
            <p className="step-card-desc">{STEPS[selectedStep].description}</p>

            <div className="step-nav-arrows">
              <button
                type="button"
                className="step-arrow-btn"
                disabled={selectedStep === 0}
                onClick={() => setSelectedStep((prev) => Math.max(0, prev - 1))}
                aria-label="Previous step"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M19 12H5M12 19l-7-7 7-7" />
                </svg>
                Previous Stage
              </button>
              <button
                type="button"
                className="step-arrow-btn"
                disabled={selectedStep === STEPS.length - 1}
                onClick={() => setSelectedStep((prev) => Math.min(STEPS.length - 1, prev + 1))}
                aria-label="Next step"
              >
                Next Stage
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>

          <div className="step-card-right">
            <div className="step-terminal-window">
              <div className="step-terminal-chrome">
                <div className="chrome-dots">
                  <span className="dot red" />
                  <span className="dot yellow" />
                  <span className="dot green" />
                </div>
                <span className="chrome-label">pipeline_trace.log — stage_{STEPS[selectedStep].step.toLowerCase()}</span>
              </div>
              <pre className="step-terminal-code">
                <code>{STEPS[selectedStep].codeSnippet}</code>
              </pre>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
