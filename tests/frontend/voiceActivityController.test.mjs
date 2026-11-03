import assert from 'node:assert/strict'
import { createVoiceActivityDetector, transcribeVoiceSegment } from '../../frontend/src/voice/voiceActivityController.js'

function frame(amplitude, length = 2048) {
  const values = new Float32Array(length)
  for (let index = 0; index < length; index += 1) {
    values[index] = amplitude * Math.sin((2 * Math.PI * 440 * index) / 48000)
  }
  return values
}

function runFrames(detector, amplitude, count) {
  for (let index = 0; index < count; index += 1) detector.processFrame(frame(amplitude))
}

const utterances = []
let speechStarts = 0
const detector = createVoiceActivityDetector({
  sampleRate: 48000,
  onSpeechStart: () => { speechStarts += 1 },
  onUtterance: (blob, details) => utterances.push({ blob, details }),
})

// A short loud transient must not be treated as a spoken interruption.
runFrames(detector, 0.08, 2)
assert.equal(speechStarts, 0)
assert.equal(utterances.length, 0)

// Sustained voice crosses the debounce threshold and starts one utterance.
runFrames(detector, 0.08, 10)
assert.equal(speechStarts, 1)
assert.equal(detector.isSpeaking, true)

// Silence closes the utterance and produces a valid WAV recording.
runFrames(detector, 0.0001, 22)
assert.equal(detector.isSpeaking, false)
assert.equal(utterances.length, 1)
assert.equal(utterances[0].blob.type, 'audio/wav')
assert.ok(utterances[0].blob.size > 44)
assert.ok(utterances[0].details.speechMs >= 320)

detector.dispose()

let requestSeen = null
const transcript = await transcribeVoiceSegment(new Blob([new Uint8Array(64)], { type: 'audio/wav' }), async (url, options) => {
  requestSeen = { url, options }
  return { ok: true, json: async () => ({ ok: true, text: 'Open the European Union website.' }) }
})
assert.equal(transcript, 'Open the European Union website.')
assert.equal(requestSeen.options.method, 'POST')
assert.equal(requestSeen.options.headers['Content-Type'], 'audio/wav')
assert.ok(requestSeen.url.endsWith('/api/voice/transcribe'))

console.log('NOVA voice activity controller tests passed.')
