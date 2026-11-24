import React, { useState, useRef, useEffect } from 'react';
import './ModelSelector.css';

function SparkleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
      <path d="M5 3v4" />
      <path d="M19 17v4" />
      <path d="M3 5h4" />
      <path d="M17 19h4" />
    </svg>
  );
}

function BrowserIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
      <path d="M2 12h20" />
    </svg>
  );
}

function DesktopIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect width="20" height="14" x="2" y="3" rx="2" />
      <line x1="8" x2="16" y1="21" y2="21" />
      <line x1="12" x2="12" y1="17" y2="21" />
    </svg>
  );
}

function CoderIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function BronzeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c89658" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

const MODES = [
  { id: 'auto', label: 'Auto', description: 'Intelligent multi-agent routing', icon: SparkleIcon },
  { id: 'browser', label: 'Browser', description: 'Direct web & browser automation', icon: BrowserIcon },
  { id: 'desktop', label: 'Desktop', description: 'Direct Windows desktop automation', icon: DesktopIcon },
  { id: 'coder', label: 'Coder', description: 'DeepSeek-Hardness coding & workspace tools', icon: CoderIcon },
  { id: 'bronze', label: 'NOVA Bronze', description: 'Fast on-device local Bronze engine', icon: BronzeIcon },
];

export default function ModelSelector({ currentMode = 'auto', onSelectMode, className = '', dropUp = false }) {
  const [isOpen, setIsOpen] = useState(false);
  const [placement, setPlacement] = useState('up'); // Default UP to avoid dropping below suggestions
  const containerRef = useRef(null);

  const selected = MODES.find((m) => m.id === currentMode) || MODES[0];
  const CurrentIcon = selected.icon;

  useEffect(() => {
    if (isOpen && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;
      // If dropUp is explicitly true, or if space below is tighter than 260px, or space above is larger, open UP!
      if (dropUp || spaceBelow < 260 || spaceAbove > spaceBelow) {
        setPlacement('up');
      } else {
        setPlacement('down');
      }
    }
  }, [isOpen, dropUp]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const handleSelect = (modeId) => {
    onSelectMode?.(modeId);
    setIsOpen(false);
  };

  return (
    <div className={`model-selector-wrapper ${className}`} ref={containerRef}>
      <button
        type="button"
        className={`model-selector-trigger ${isOpen ? 'is-open' : ''} ${selected.id === 'bronze' ? 'is-bronze' : ''}`}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={`Agent execution mode: ${selected.label}. Click to switch.`}
      >
        <span className="model-selector-trigger-icon">
          <CurrentIcon />
        </span>
        <span className="model-selector-trigger-label">{selected.label}</span>
        <span className={`model-selector-trigger-arrow ${isOpen ? 'is-rotated' : ''}`}>
          <ChevronDownIcon />
        </span>
      </button>

      {isOpen && (
        <div
          className={`model-selector-dropdown ${placement === 'up' ? 'drop-up' : 'drop-down'}`}
          role="listbox"
          aria-label="Select execution mode"
        >
          <div className="model-selector-dropdown-header">Execution Mode</div>
          {MODES.map((mode) => {
            const isSelected = mode.id === currentMode;
            const Icon = mode.icon;
            return (
              <button
                key={mode.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                className={`model-selector-dropdown-item ${isSelected ? 'is-active' : ''} ${mode.id === 'bronze' ? 'is-bronze-item' : ''}`}
                onClick={() => handleSelect(mode.id)}
              >
                <span className="model-selector-item-icon">
                  <Icon />
                </span>
                <div className="model-selector-item-content">
                  <span className="model-selector-item-title">{mode.label}</span>
                  <span className="model-selector-item-desc">{mode.description}</span>
                </div>
                {isSelected && (
                  <span className="model-selector-item-check">
                    <CheckIcon />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
