import test from 'node:test'
import assert from 'node:assert/strict'
import { createVoicePlaybackQueue } from '../../frontend/src/voice/voicePlaybackQueue.js'

function createAudioContext() {
  const context = {
    currentTime: 0,
    state: 'running',
    destination: {},
    createdSources: [],
    createBufferSource() {
      const source = {
        playbackRate: { value: 1 },
        startCalls: [],
        connect() {},
        disconnect() {},
        start(...args) { this.startCalls.push(args) },
        stop() {},
        onended: null,
      }
      this.createdSources.push(source)
      return source
    },
    decodeAudioData: async () => ({ duration: 4 }),
    resume: async () => {},
  }
  return context
}

test('voice playback queue clamps the requested playback rate', async () => {
  const context = createAudioContext()
  const queue = createVoicePlaybackQueue({
    audioContext: context,
    playbackRate: 2,
    request: async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(8) }),
  })
  queue.start('Hello.')
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(context.createdSources[0]?.playbackRate.value, 1.25)
  queue.cancel()
})

test('voice playback queue supports slower playback without changing audio generation payload', async () => {
  const context = createAudioContext()
  let requestBody
  const queue = createVoicePlaybackQueue({
    audioContext: context,
    playbackRate: 0.85,
    request: async (_url, options) => {
      requestBody = JSON.parse(options.body)
      return { ok: true, arrayBuffer: async () => new ArrayBuffer(8) }
    },
  })
  queue.start('Hello.')
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(context.createdSources[0]?.playbackRate.value, 0.85)
  assert.deepEqual(requestBody, { text: 'Hello.' })
  queue.cancel()
})


test('pause and resume offsets account for the selected playback rate', async () => {
  const context = createAudioContext()
  const queue = createVoicePlaybackQueue({
    audioContext: context,
    playbackRate: 1.25,
    request: async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(8) }),
  })
  queue.start('One sentence.')
  await new Promise((resolve) => setTimeout(resolve, 0))
  context.currentTime = 1
  assert.equal(queue.pause(), true)
  context.currentTime = 2
  assert.equal(queue.resume(), true)
  assert.equal(context.createdSources.length, 2)
  assert.equal(context.createdSources[1].startCalls[0][1], 1.25)
  queue.cancel()
})
