import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const app = await readFile(new URL('../../frontend/src/App.jsx', import.meta.url), 'utf8')

test('Voice Mode primes a live TTS queue before submitting the task and finishes it after the final delta', () => {
  assert.match(app, /const voiceStreamingEnabled = Boolean\(sourceOptions\.fromVoiceMode && speakThisVoiceReply\)/)
  assert.match(app, /void readAloudResponse\('', voiceStreamKey, selectedVoiceProfileId, true, voiceStreamLanguage\)/)
  const primeAt = app.indexOf("void readAloudResponse('', voiceStreamKey")
  const submitAt = app.indexOf("fetch('http://127.0.0.1:8000/api/task'")
  assert.ok(primeAt >= 0 && submitAt > primeAt, 'TTS queue must be ready before the task is submitted')
  assert.match(app, /voicePlaybackQueueRef\.current\?\.finishInput\?\.\(\)/)
  assert.match(app, /voicePlaybackQueueRef\.current\?\.appendText\?\.\(delta\)/)
})

test('a new Voice Mode task clears the prior-session cancellation flag before streaming', () => {
  assert.match(app, /if \(sourceOptions\.fromVoiceMode\) \{[\s\S]{0,420}voiceStreamSessionCancelledRef\.current = false/)
})

test('muting the mic changes capture and resumes paused output without cancelling the playback queue', () => {
  const muteEffectStart = app.indexOf('if (!voiceModeMicEnabled) {', app.indexOf('Keep microphone mute state'))
  const muteEffectEnd = app.indexOf('} else if (voiceModeOpen && stream) {', muteEffectStart)
  const muteEffect = app.slice(muteEffectStart, muteEffectEnd)
  assert.match(muteEffect, /playbackQueue\?\.isPaused\?\.\(\)\) playbackQueue\.resume\(\)/)
  assert.match(muteEffect, /playbackQueue\?\.isPlaying\?\.\(\)\) setVoiceRoomStatus\('speaking'\)/)
  assert.doesNotMatch(muteEffect, /stopReadAloud|\.cancel\(|\.dispose\(/)
})
