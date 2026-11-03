import test from 'node:test'
import assert from 'node:assert/strict'
import { createVoicePlaybackQueue } from '../../frontend/src/voice/voicePlaybackQueue.js'

class FakeAudioContext {
  state = 'running'
  currentTime = 0
  destination = {}

  async decodeAudioData(bytes) {
    assert.ok(bytes instanceof ArrayBuffer)
    return { duration: 0.05 }
  }

  createBufferSource() {
    const source = {
      buffer: null,
      playbackRate: { value: 1 },
      connect() {},
      disconnect() {},
      stop() {},
      start: () => queueMicrotask(() => source.onended?.()),
      onended: null,
    }
    return source
  }

  async resume() { this.state = 'running' }
}

test('sends generated NOVA response text to Voicebox with the selected profile and plays returned audio', async () => {
  const requests = []
  const states = []
  const queue = createVoicePlaybackQueue({
    audioContext: new FakeAudioContext(),
    profileId: 'profile-42',
    language: 'en',
    request: async (url, options) => {
      requests.push({ url, options, body: JSON.parse(options.body) })
      return { ok: true, arrayBuffer: async () => new ArrayBuffer(8) }
    },
    onState: (state) => states.push(state),
  })

  await queue.start('Hello. This is NOVA speaking.')

  assert.ok(requests.length >= 1)
  assert.equal(requests[0].url, 'http://127.0.0.1:8000/api/voice/speak')
  assert.equal(requests[0].body.profile_id, 'profile-42')
  assert.equal(requests[0].body.language, 'en')
  assert.match(requests[0].body.text, /Hello\./)
  assert.ok(states.includes('speaking'))
  assert.ok(states.includes('complete'))
})


test('reports an SVG response as a non-audio Voicebox response', async () => {
  const queue = createVoicePlaybackQueue({
    audioContext: new FakeAudioContext(),
    request: async () => ({
      ok: true,
      headers: { get: () => 'image/svg+xml' },
      arrayBuffer: async () => new ArrayBuffer(8),
    }),
  })

  await assert.rejects(queue.start('Hello from NOVA.'), /received image\/svg\+xml.*cannot be played as speech/i)
})

test('explains a failed fetch to the Voicebox speech endpoint', async () => {
  const queue = createVoicePlaybackQueue({
    audioContext: new FakeAudioContext(),
    request: async () => { throw new TypeError('Failed to fetch') },
  })

  await assert.rejects(queue.start('Hello from NOVA.'), /could not reach its Voicebox speech endpoint.*Failed to fetch/i)
})
