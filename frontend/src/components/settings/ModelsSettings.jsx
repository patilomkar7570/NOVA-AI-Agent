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

  // Fetch model settings on mount
  useEffect(() => {
    let active = true;
    async function loadSettings() {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/settings/models');
        if (!res.ok) throw new Error('Failed to load settings');
        const data = await res.json();
        if (active && data.ok) {
          setModelSettings(data.settings);
          setAvailableGemini(data.available_gemini_models || []);
          setAvailableLocal(data.available_local_models || []);
          setApiKeyInput(data.settings?.gemini_api_key || '');
        }
      } catch (err) {
        console.debug('Failed to fetch model settings:', err);
      } finally {
        if (active) setLoading(false);
      }
    }
    loadSettings();
    return () => { active = false; };
  }, []);

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
      {/* 1. AGENT EXECUTION MODE SELECTOR */}
      <section className="settings-card">
        <div className="settings-card-copy">
          <span className="settings-card-label">EXECUTION STRATEGY</span>
          <h2>Agent Execution Mode</h2>
          <p>
            Choose the default routing for your instructions. You can also quickly toggle this from the prompt bar dropdown.
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', width: '100%', marginTop: '6px' }}>
          <button
            type="button"
            className={`settings-mode-btn ${agentMode === 'auto' ? 'selected' : ''}`}
            onClick={() => onSelectMode?.('auto')}
          >
            <div className="settings-mode-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>✨</span> Auto Mode
            </div>
            <div className="settings-mode-desc">
              Intelligent multi-agent routing between chat, research, coder, browser, or desktop specialists.
            </div>
          </button>

          <button
            type="button"
            className={`settings-mode-btn ${agentMode === 'browser' ? 'selected' : ''}`}
            onClick={() => onSelectMode?.('browser')}
          >
            <div className="settings-mode-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>🌐</span> Browser Mode
            </div>
            <div className="settings-mode-desc">
              Routes directly to the dedicated Brave / Playwright Browser Specialist for web navigation.
            </div>
          </button>

          <button
            type="button"
            className={`settings-mode-btn ${agentMode === 'desktop' ? 'selected' : ''}`}
            onClick={() => onSelectMode?.('desktop')}
          >
            <div className="settings-mode-title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>🖥️</span> Desktop Mode
            </div>
            <div className="settings-mode-desc">
              Routes directly to the Computer Specialist for native Windows UI automation and application control.
            </div>
          </button>
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
