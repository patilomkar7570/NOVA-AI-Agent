import test from 'node:test'
import assert from 'node:assert/strict'
import { getVoiceOrbState, getVoiceStatusLabel } from '../../frontend/src/voice/voiceUiState.js'

test('maps voice lifecycle states to supported Mercury Orb states', () => {
  assert.equal(getVoiceOrbState('requesting'), 'connecting')
  assert.equal(getVoiceOrbState('thinking'), 'thinking')
  assert.equal(getVoiceOrbState('speaking'), 'speaking')
  assert.equal(getVoiceOrbState('interrupted'), 'listening')
  assert.equal(getVoiceOrbState('ready'), 'listening')
  assert.equal(getVoiceOrbState('paused'), 'idle')
  assert.equal(getVoiceOrbState('unavailable'), 'error')
  assert.equal(getVoiceOrbState('muted', true), 'disabled')
  assert.equal(getVoiceOrbState('speaking', false), 'speaking')
  assert.equal(getVoiceOrbState('thinking', false), 'thinking')
  assert.equal(getVoiceOrbState('ready', false), 'disabled')
})

test('status text is understandable and reports permission/service errors', () => {
  assert.equal(getVoiceStatusLabel('thinking'), 'NOVA is thinking…')
  assert.equal(getVoiceStatusLabel('speaking'), 'NOVA is speaking…')
  assert.match(getVoiceStatusLabel('paused'), /Speech paused/)
  assert.match(getVoiceStatusLabel('permission'), /Allow microphone access/)
  assert.equal(getVoiceStatusLabel('unavailable', true, 'Voicebox is offline.'), 'Voicebox is offline.')
  assert.equal(getVoiceStatusLabel('ready'), 'Listening for your next message…')
  assert.equal(getVoiceStatusLabel('speaking', false), 'NOVA is speaking…')
  assert.equal(getVoiceStatusLabel('thinking', false), 'NOVA is thinking…')
  assert.equal(getVoiceStatusLabel('ready', false), 'Microphone muted')
})
