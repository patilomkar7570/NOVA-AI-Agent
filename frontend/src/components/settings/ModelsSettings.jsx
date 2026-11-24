import React, { useState, useEffect } from 'react';

export default function ModelsSettings({ agentMode, onSelectMode }) {
  const [modelSettings, setModelSettings] = useState(null);
  const [availableGemini, setAvailableGemini] = useState([]);
  const [availableLocal, setAvailableLocal] = useState([]);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [testStatus, setTestStatus] = useState(null); // { state: 'testing' | 'success' | 'error', message: '' }
  const [saveStatus, setSaveStatus] = useState(null); // { state: 'saving' | 'saved' | 'error', message: '' }
  const [loading, setLoading] = useState(true);
  const [coderPerms, setCoderPerms] = useState({
    current_stage: 'necessary',
    available_stages: [
      {
        id: 'minimal',
        label: 'Stage 1: Minimal (Read-Only)',
        summary: 'Safe AST syntax check & code diff inspection without disk modifications.',
        hover_info: 'Read-Only Inspection Mode: Allows CoderAgent to read files and inspect syntax, but strictly blocks any file modifications, unified diff writing, package installations, or shell/test executions on disk.',
      },
      {
        id: 'necessary',
        label: 'Stage 2: Necessary (Workspace Protected - Recommended)',
        summary: 'Full read, write, patch, and test execution restricted strictly to the project workspace.',
        hover_info: 'Balanced Workspace Development (Recommended): Permits reading, writing, patching, and running test suites strictly within the current project workspace repository. Access outside the workspace root and modifications to OS/system drives are strictly prohibited.',
      },
      {
        id: 'all',
        label: 'Stage 3: All (Full Autonomous Developer)',
        summary: 'Unrestricted developer autonomy with multi-file edits, Git worktree isolation, and external access.',
        hover_info: 'Full Autonomous Developer Mode: Grants unrestricted multi-file editing, Git worktree isolation, package management (pip/npm), and system-level test execution across workspace and linked directories under automated safety policy guardrails.',
      },
    ],
  });
  const [coderPermStatus, setCoderPermStatus] = useState(null);

  // Fetch model settings and coder permissions on mount
  useEffect(() => {
    let active = true;
    async function loadSettings() {
      try {
        const [modelsRes, permsRes] = await Promise.all([
          fetch('http://127.0.0.1:8000/api/settings/models').catch(() => null),
          fetch('http://127.0.0.1:8000/api/settings/coder-permissions').catch(() => null),
        ]);
        if (active && modelsRes && modelsRes.ok) {
          const data = await modelsRes.json();
          if (data.ok) {
            setModelSettings(data.settings);
            setAvailableGemini(data.available_gemini_models || []);
            setAvailableLocal(data.available_local_models || []);
            setApiKeyInput(data.settings?.gemini_api_key || '');
          }
        }
        if (active && permsRes && permsRes.ok) {
          const pData = await permsRes.json();
          if (pData.ok) {
            setCoderPerms(pData);
          }
        }
      } catch (err) {
        console.debug('Failed to fetch settings:', err);
      } finally {
        if (active) setLoading(false);
      }
    }
    loadSettings();
    return () => { active = false; };
  }, []);

  const handleSelectCoderStage = async (stageId) => {
    setCoderPermStatus({ state: 'saving', message: 'Updating permission stage…' });
    try {
      const res = await fetch('http://127.0.0.1:8000/api/settings/coder-permissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: stageId }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setCoderPerms((prev) => ({ ...prev, current_stage: data.current_stage }));
        setCoderPermStatus({ state: 'saved', message: `Coder permissions set to Stage: ${data.current_stage.toUpperCase()}` });
        setTimeout(() => setCoderPermStatus(null), 3000);
      } else {
        setCoderPermStatus({ state: 'error', message: data.error || 'Failed to update stage.' });
      }
    } catch (err) {
      setCoderPermStatus({ state: 'error', message: `Update error: ${err.message}` });
    }
  };

  const handleTestApiKey = async () => {
    setTestStatus({ state: 'testing', message: 'Testing Gemini API key connection…' });
    try {
      const res = await fetch('http://127.0.0.1:8000/api/settings/models/test-gemini', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeyInput, model: 'gemini-2.5-flash' }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setTestStatus({
          state: 'success',
          message: data.message || `Connected successfully (${data.latency_ms || 180}ms latency).`,
        });
      } else {
        setTestStatus({
          state: 'error',
          message: data.error || 'Connection failed. Check your API key and try again.',
        });
      }
    } catch (err) {
      setTestStatus({ state: 'error', message: `Network error: ${err.message}` });
    }
  };

  const handleSaveSettings = async (overrides = {}) => {
    setSaveStatus({ state: 'saving', message: 'Saving configuration…' });
    const payload = {
      ...(modelSettings || {}),
      gemini_api_key: apiKeyInput,
      ...overrides,
    };
    try {
      const res = await fetch('http://127.0.0.1:8000/api/settings/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setModelSettings(data.settings);
        setSaveStatus({ state: 'saved', message: 'Model settings saved successfully!' });
        setTimeout(() => setSaveStatus(null), 3000);
      } else {
        setSaveStatus({ state: 'error', message: data.error || 'Failed to save settings.' });
      }
    } catch (err) {
      setSaveStatus({ state: 'error', message: `Save error: ${err.message}` });
    }
  };

  const updateRoleConfig = (roleKey, field, value) => {
    setModelSettings((prev) => {
      const currentRole = prev?.[roleKey] || {};
      const updatedRole = { ...currentRole, [field]: value };
      const updated = { ...prev, [roleKey]: updatedRole };
      return updated;
    });
  };

  return (
    <div className="settings-tab-content" role="tabpanel">
      {/* CODER AGENT PERMISSION TIERS (3 STAGES) */}
      <section className="settings-card" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
        <div className="settings-card-copy" style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <div>
              <span className="settings-card-label">SECURITY & ACCESS CONTROL</span>
              <h2>Coder Agent Permissions (3 Stages)</h2>
              <p>
                Select your security tier below. Hover over any stage for detailed policy information.
              </p>
            </div>
            {coderPermStatus && (
              <span style={{
                fontSize: '12px',
                padding: '4px 10px',
                borderRadius: '6px',
                background: coderPermStatus.state === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
                color: coderPermStatus.state === 'error' ? '#ef4444' : '#22c55e',
                border: `1px solid ${coderPermStatus.state === 'error' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
              }}>
                {coderPermStatus.message}
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', width: '100%', marginTop: '14px' }}>
          {[
            {
              id: 'minimal',
              name: 'Minimal',
              tag: 'Read-Only',
              desc: 'Safe inspection & diff viewing. Zero file writes or executions.',
              tooltip: 'Stage 1 (Minimal): Allows CoderAgent to read workspace files and validate AST syntax, but strictly blocks any file modifications or subprocess executions.',
            },
            {
              id: 'necessary',
              name: 'Necessary',
              tag: 'Recommended',
              desc: 'Workspace protected. Read, write, and test inside project only.',
              tooltip: 'Stage 2 (Necessary): Permits reading, writing, and test execution strictly within the current workspace. Blocks OS system drives and external folders.',
            },
            {
              id: 'all',
              name: 'All',
              tag: 'Full PC Access',
              desc: 'Full developer power across your whole PC with developer tools.',
              tooltip: 'Stage 3 (All): Grants unrestricted whole-PC file access, multi-file edits, Git worktree isolation, and system test execution under automated safety policies.',
            },
          ].map((stage) => {
            const isSelected = (coderPerms?.current_stage || 'necessary') === stage.id;
            return (
              <div
                key={stage.id}
                role="button"
                tabIndex={0}
                className={`coder-stage-pill ${isSelected ? 'is-selected' : ''}`}
                onClick={() => handleSelectCoderStage(stage.id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleSelectCoderStage(stage.id); }}
                title={stage.tooltip}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 700, fontSize: '13px', color: isSelected ? '#c89658' : 'inherit' }}>
                    {stage.name}
                  </span>
                  <span style={{
                    fontSize: '11px',
                    padding: '2px 7px',
                    borderRadius: '4px',
                    background: isSelected ? 'rgba(200, 150, 88, 0.25)' : 'rgba(255, 255, 255, 0.08)',
                    color: isSelected ? '#c89658' : 'rgba(255, 255, 255, 0.6)',
                    fontWeight: 600,
                  }}>
                    {isSelected ? '✓ ' + stage.tag : stage.tag}
                  </span>
                </div>
                <div className="coder-stage-desc">
                  {stage.desc}
                </div>
                {/* Pure CSS zero-latency tooltip directly on cursor */}
                <div className="coder-stage-tooltip" role="tooltip">
                  <strong>{stage.name} ({stage.tag})</strong>
                  <div style={{ marginTop: '4px' }}>{stage.tooltip}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 2. GOOGLE GEMINI CLOUD CONFIGURATION */}
      <section className="settings-card settings-gemini-card">
        <div className="settings-card-copy">
          <span className="settings-card-label">CLOUD INFERENCE</span>
          <h2>Google Gemini API Key</h2>
          <p>
            Connect Google Gemini for high-speed cloud reasoning and multimodal perception.
          </p>
        </div>

        <div className="settings-gemini-controls">
          <div className="settings-api-key-input-row">
            <div className="settings-key-field-wrapper">
              <input
                type={showApiKey ? 'text' : 'password'}
                className="settings-api-key-input"
                placeholder="Enter your Gemini API key (AQ.Ab8...)"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                aria-label="Gemini API Key"
              />
              <button
                type="button"
                className="settings-key-reveal-btn"
                onClick={() => setShowApiKey((prev) => !prev)}
                title={showApiKey ? 'Hide API key' : 'Show API key'}
                aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
              >
                {showApiKey ? '👁️' : '🔒'}
              </button>
            </div>

            <div className="settings-key-actions">
              <button
                type="button"
                className="settings-btn-secondary"
                onClick={handleTestApiKey}
                disabled={!apiKeyInput.trim() || testStatus?.state === 'testing'}
              >
                {testStatus?.state === 'testing' ? 'Testing…' : 'Test Key'}
              </button>
              <button
                type="button"
                className="settings-btn-primary"
                onClick={() => handleSaveSettings({ gemini_api_key: apiKeyInput })}
                disabled={saveStatus?.state === 'saving'}
              >
                {saveStatus?.state === 'saving' ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>

          {testStatus && (
            <div className={`settings-api-test-badge ${testStatus.state}`}>
              <span>{testStatus.state === 'success' ? '✓' : testStatus.state === 'testing' ? '⏳' : '✕'}</span>
              <span>{testStatus.message}</span>
            </div>
          )}

          {saveStatus && (
            <div className={`settings-api-test-badge ${saveStatus.state === 'saved' ? 'success' : 'error'}`}>
              <span>{saveStatus.state === 'saved' ? '✓' : '✕'}</span>
              <span>{saveStatus.message}</span>
            </div>
          )}
        </div>
      </section>

      {/* 3. CHAT MODEL SELECTOR */}
      <section className="settings-card settings-role-card">
        <div className="settings-role-header">
          <div className="settings-card-copy">
            <span className="settings-card-label">CONVERSATIONAL MODEL</span>
            <h2>Chat & General Responses</h2>
            <p>Model used for casual conversations, greeting queries, and voice transcript generation.</p>
          </div>
        </div>

        <div className="settings-role-body">
          <div className="settings-role-provider-row">
            <span className="settings-sublabel">Provider</span>
            <div className="settings-provider-pills">
              <button
                type="button"
                className={`settings-provider-pill ${modelSettings?.chat_model?.provider === 'gemini' ? 'selected' : ''}`}
                onClick={() => updateRoleConfig('chat_model', 'provider', 'gemini')}
              >
                Google Gemini Cloud
              </button>
              <button
                type="button"
                className={`settings-provider-pill ${modelSettings?.chat_model?.provider === 'local' ? 'selected' : ''}`}
                onClick={() => updateRoleConfig('chat_model', 'provider', 'local')}
              >
                Local Qwen (Ollama)
              </button>
            </div>
          </div>

          <div className="settings-role-model-row">
            <span className="settings-sublabel">Model Selection</span>
            {modelSettings?.chat_model?.provider === 'gemini' ? (
              <select
                className="settings-model-select"
                value={modelSettings?.chat_model?.gemini_model || 'gemini-3.5-flash-lite'}
                onChange={(e) => updateRoleConfig('chat_model', 'gemini_model', e.target.value)}
                aria-label="Gemini Chat Model"
              >
                {availableGemini.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} {m.recommended_for?.includes('chat') ? '★ Recommended' : ''}
                  </option>
                ))}
              </select>
            ) : (
              <select
                className="settings-model-select"
                value={modelSettings?.chat_model?.local_model || 'qwen3:1.7b'}
                onChange={(e) => updateRoleConfig('chat_model', 'local_model', e.target.value)}
                aria-label="Local Chat Model"
              >
                {availableLocal.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} {m.recommended_for?.includes('chat') ? '★ Recommended' : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
      </section>

      {/* 4. WORK & PLANNING MODEL SELECTOR */}
      <section className="settings-card settings-role-card">
        <div className="settings-role-header">
          <div className="settings-card-copy">
            <span className="settings-card-label">PLANNING & WORK SPECIALIST MODEL</span>
            <h2>Work & Multi-Agent Planning</h2>
            <p>Model used for plan synthesis, browser observation, code generation, and complex tasks.</p>
          </div>
        </div>

        <div className="settings-role-body">
          <div className="settings-role-provider-row">
            <span className="settings-sublabel">Provider</span>
            <div className="settings-provider-pills">
              <button
                type="button"
                className={`settings-provider-pill ${modelSettings?.work_model?.provider === 'gemini' ? 'selected' : ''}`}
                onClick={() => updateRoleConfig('work_model', 'provider', 'gemini')}
              >
                Google Gemini Cloud
              </button>
              <button
                type="button"
                className={`settings-provider-pill ${modelSettings?.work_model?.provider === 'local' ? 'selected' : ''}`}
                onClick={() => updateRoleConfig('work_model', 'provider', 'local')}
              >
                Local Qwen (Ollama)
              </button>
            </div>
          </div>

          <div className="settings-role-model-row">
            <span className="settings-sublabel">Model Selection</span>
            {modelSettings?.work_model?.provider === 'gemini' ? (
              <select
                className="settings-model-select"
                value={modelSettings?.work_model?.gemini_model || 'gemini-3.5-flash-lite'}
                onChange={(e) => updateRoleConfig('work_model', 'gemini_model', e.target.value)}
                aria-label="Gemini Work Model"
              >
                {availableGemini.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} {m.recommended_for?.includes('work') ? '★ Recommended' : ''}
                  </option>
                ))}
              </select>
            ) : (
              <select
                className="settings-model-select"
                value={modelSettings?.work_model?.local_model || 'qwen3:8b'}
                onChange={(e) => updateRoleConfig('work_model', 'local_model', e.target.value)}
                aria-label="Local Work Model"
              >
                {availableLocal.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} {m.recommended_for?.includes('work') ? '★ Recommended' : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
          <button
            type="button"
            className="settings-btn-primary"
            onClick={() => handleSaveSettings()}
            disabled={saveStatus?.state === 'saving'}
          >
            {saveStatus?.state === 'saving' ? 'Saving…' : 'Save All Model Settings'}
          </button>
        </div>
      </section>
    </div>
  );
}
