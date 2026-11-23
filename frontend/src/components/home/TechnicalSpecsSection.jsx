import { useState } from 'react'

const SPECS_DATA = [
  {
    category: 'Operating System',
    min: 'Windows 10 22H2 (64-bit)',
    rec: 'Windows 11 (64-bit, Build 22621+)',
    notes: 'Native Windows shell integration and desktop automation support.'
  },
  {
    category: 'System Memory (RAM)',
    min: '16 GB RAM',
    rec: '32 GB DDR4 / DDR5 RAM',
    notes: '16 GB supports dual-model local setups; 8 GB suffices for single lightweight models or cloud fallback.'
  },
  {
    category: 'Local Storage',
    min: '20 GB Available NVMe / SSD',
    rec: '50 GB+ High-Speed SSD',
    notes: 'Accommodates virtual environments, Ollama GGUF weights, Voicebox audio models, and temporary files.'
  },
  {
    category: 'Processor & Acceleration',
    min: 'Intel Core i5 / AMD Ryzen 5 (6 Cores)',
    rec: 'Intel Core i7/i9 or AMD Ryzen 7/9 + NVIDIA GPU (8 GB+ VRAM)',
    notes: 'Ollama leverages NVIDIA CUDA or DirectML for real-time token streaming. CPU fallback is supported.'
  },
  {
    category: 'Python Runtime',
    min: 'CPython 3.10+',
    rec: 'CPython 3.14.7 (Pinned for Beta 0.6)',
    notes: 'Virtual environment managed via standard venv or official Python Install Manager (pymanager).'
  },
  {
    category: 'Frontend & Node.js',
    min: 'Node.js 18.x LTS',
    rec: 'Node.js 20.x or 22.x LTS + npm 10+',
    notes: 'Powers the React 19 workstation interface with Vite 8.3 development & build pipelines.'
  },
  {
    category: 'Browser Automation',
    min: 'Playwright Chromium',
    rec: 'Brave Browser / Microsoft Edge / Chromium',
    notes: 'Dedicated automated browser worker for live website navigation, DOM parsing, and research.'
  },
  {
    category: 'Audio & Speech Hardware',
    min: 'Standard Microphone & Speakers',
    rec: 'Low-noise USB Condenser Mic + Headphones',
    notes: 'Voicebox acoustic engine handles speech synthesis; Whisper or browser engine captures voice input.'
  }
]

export default function TechnicalSpecsSection() {
  const [viewMode, setViewMode] = useState('recommended') // 'minimum' | 'recommended' | 'all'

  return (
    <section className="luxury-section tech-specs-section" id="specs">
      <div className="luxury-section-header">
        <div className="luxury-section-badge">
          <span className="badge-pulse" />
          SYSTEM REQUIREMENTS • ALPHA 0.5
        </div>
        <h2 className="luxury-section-title">
          Engineered for modern workstation hardware.
        </h2>
        <p className="luxury-section-subtitle">
          NOVA is architected to extract peak efficiency from your local PC. Review the verified system specifications below
          to prepare your environment for Beta 0.6.
        </p>
      </div>

      <div className="specs-card-container">
        {/* Toggle Mode Bar */}
        <div className="specs-toggle-bar">
          <div className="specs-filter-group" role="radiogroup" aria-label="System requirement tier">
            <button
              type="button"
              className={`specs-filter-btn ${viewMode === 'recommended' ? 'is-active' : ''}`}
              onClick={() => setViewMode('recommended')}
            >
              Recommended Workstation
            </button>
            <button
              type="button"
              className={`specs-filter-btn ${viewMode === 'minimum' ? 'is-active' : ''}`}
              onClick={() => setViewMode('minimum')}
            >
              Minimum Baseline
            </button>
            <button
              type="button"
              className={`specs-filter-btn ${viewMode === 'all' ? 'is-active' : ''}`}
              onClick={() => setViewMode('all')}
            >
              Side-by-Side Comparison
            </button>
          </div>

          <span className="specs-release-pill">Beta Build v0.6.0</span>
        </div>

        {/* Specs Minimal Grid */}
        <div className="specs-grid">
          {SPECS_DATA.map((spec, idx) => (
            <div key={idx} className="spec-row-item">
              <div className="spec-category-cell">
                <span className="spec-cat-name">{spec.category}</span>
                <span className="spec-cat-notes">{spec.notes}</span>
              </div>

              {(viewMode === 'minimum' || viewMode === 'all') && (
                <div className="spec-val-cell is-min">
                  <span className="tier-tag">MINIMUM</span>
                  <span className="spec-text">{spec.min}</span>
                </div>
              )}

              {(viewMode === 'recommended' || viewMode === 'all') && (
                <div className="spec-val-cell is-rec">
                  <span className="tier-tag">RECOMMENDED</span>
                  <span className="spec-text">{spec.rec}</span>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Technical Performance Disclaimer */}
        <div className="specs-disclaimer-box">
          <div className="disclaimer-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div className="disclaimer-copy">
            <strong>System Resource Scaling:</strong> Local neural inference and voice synthesis performance directly depend on available CPU threads, GPU VRAM (CUDA/DirectML), RAM bandwidth, and background processes. For setups with limited hardware, NOVA provides lightweight model tiers and optional cloud provider routing.
          </div>
        </div>
      </div>
    </section>
  )
}
