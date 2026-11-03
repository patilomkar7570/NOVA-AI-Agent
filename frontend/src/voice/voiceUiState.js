/**
 * Translate the voice-session lifecycle into supported Mercury Orb states and
 * user-facing status text. Keep this mapping separate so it can be regression
 * tested without mounting the full NOVA application.
 */
export function getVoiceOrbState(status, microphoneEnabled = true) {
  // Assistant output is independent from microphone capture. Keep the orb
  // animated while NOVA is thinking/speaking, even when the mic is muted.
  if (status === 'speaking') return 'speaking'
  if (status === 'thinking') return 'thinking'
  if (!microphoneEnabled || status === 'muted') return 'disabled'
  if (status === 'requesting' || status === 'connecting') return 'connecting'
  if (['permission', 'unavailable', 'error'].includes(status)) return 'error'
  if (['ready', 'listening', 'interrupted'].includes(status)) return 'listening'
  return 'idle'
}

export function getVoiceStatusLabel(status, microphoneEnabled = true, errorMessage = '') {
  // Report the assistant's active output first; a muted mic must not hide it.
  if (status === 'speaking') return 'NOVA is speaking…'
  if (status === 'thinking') return 'NOVA is thinking…'
  if (!microphoneEnabled || status === 'muted') return 'Microphone muted'
  if (status === 'requesting' || status === 'connecting') return 'Connecting microphone…'
  if (status === 'interrupted') return 'Listening to you…'
  if (status === 'paused') return 'Speech paused · Resume whenever you are ready'
  if (status === 'permission') return 'Allow microphone access in your browser'
  if (status === 'unavailable' || status === 'error') return errorMessage || 'Voice services are unavailable'
  if (errorMessage && ['ready', 'listening', 'paused'].includes(status)) return errorMessage
  if (status === 'ready' || status === 'listening') return 'Listening for your next message…'
  return 'Ready when you are'
}
