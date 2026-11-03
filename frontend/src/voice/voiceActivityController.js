const NOVA_TRANSCRIBE_URL = 'http://127.0.0.1:8000/api/voice/transcribe'
const DEFAULT_CONFIG = Object.freeze({
  startMs: 260,
  endSilenceMs: 680,
  minimumSpeechMs: 320,
  maximumUtteranceMs: 16000,
  preRollMs: 260,
  threshold: 0.018,
  minimumThreshold: 0.014,
  maximumThreshold: 0.038,
  noiseMultiplier: 3.1,
  noiseOffset: 0.008,
})

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value))
}

function calculateRms(samples) {
  let sum = 0
  for (let index = 0; index < samples.length; index += 1) {
    const value = samples[index]
    sum += value * value
  }
  return Math.sqrt(sum / Math.max(1, samples.length))
}

function mergeFrames(frames) {
  const length = frames.reduce((total, frame) => total + frame.length, 0)
  const merged = new Float32Array(length)
  let offset = 0
  for (const frame of frames) {
    merged.set(frame, offset)
    offset += frame.length
  }
  return merged
}

function downsampleAverage(input, inputRate, outputRate) {
  if (inputRate === outputRate) return input
  const ratio = inputRate / outputRate
  const outputLength = Math.floor(input.length / ratio)
  const output = new Float32Array(outputLength)
  for (let index = 0; index < outputLength; index += 1) {
    const start = Math.floor(index * ratio)
    const end = Math.min(input.length, Math.floor((index + 1) * ratio))
    let sum = 0
    for (let sourceIndex = start; sourceIndex < end; sourceIndex += 1) sum += input[sourceIndex]
    output[index] = sum / Math.max(1, end - start)
  }
  return output
}

export function encodeMonoPcm16Wav(samples, sampleRate = 16000) {
  const bytesPerSample = 2
  const dataLength = samples.length * bytesPerSample
  const buffer = new ArrayBuffer(44 + dataLength)
  const view = new DataView(buffer)
  const writeAscii = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index))
  }
  writeAscii(0, 'RIFF')
  view.setUint32(4, 36 + dataLength, true)
  writeAscii(8, 'WAVE')
  writeAscii(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * bytesPerSample, true)
  view.setUint16(32, bytesPerSample, true)
  view.setUint16(34, 16, true)
  writeAscii(36, 'data')
  view.setUint32(40, dataLength, true)

  let offset = 44
  for (let index = 0; index < samples.length; index += 1) {
    const sample = clamp(samples[index], -1, 1)
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
    offset += bytesPerSample
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

function makeWavBlob(frames, inputRate) {
  const merged = mergeFrames(frames)
  const samples = downsampleAverage(merged, inputRate, 16000)
  return encodeMonoPcm16Wav(samples, 16000)
}

/**
 * Small, dependency-free VAD segmenter. Feed it microphone PCM frames and it
 * calls onSpeechStart once per utterance and onUtterance with a 16 kHz WAV blob
 * after sustained silence. This class is intentionally exported for tests.
 */
export function createVoiceActivityDetector({
  sampleRate = 48000,
  onSpeechStart = () => {},
  onUtterance = () => {},
  onLevel = () => {},
  isEnabled = () => true,
  config = {},
} = {}) {
  const options = { ...DEFAULT_CONFIG, ...config }
  const frameMs = (frameLength) => (frameLength / sampleRate) * 1000
  const maxPreRollFrames = Math.max(1, Math.ceil(options.preRollMs / (2048 / sampleRate * 1000)))
  let preRoll = []
  let candidateFrames = []
  let segmentFrames = []
  let candidateSpeechMs = 0
  let silenceMs = 0
  let segmentSpeechMs = 0
  let segmentTotalMs = 0
  let noiseFloor = 0.0035
  let active = false
  let disposed = false

  const thresholdNow = () => clamp(
    Math.max(options.threshold, noiseFloor * options.noiseMultiplier + options.noiseOffset),
    options.minimumThreshold,
    options.maximumThreshold,
  )

  const safeCallback = (callback, ...args) => {
    try {
      const result = callback?.(...args)
      if (result && typeof result.catch === 'function') result.catch((error) => console.debug('[NOVA VAD] callback failed:', error))
    } catch (error) {
      console.debug('[NOVA VAD] callback failed:', error)
    }
  }

  const resetSegment = () => {
    active = false
    preRoll = []
    candidateFrames = []
    segmentFrames = []
    candidateSpeechMs = 0
    silenceMs = 0
    segmentSpeechMs = 0
    segmentTotalMs = 0
  }

  const flush = () => {
    const frames = segmentFrames
    const speechMs = segmentSpeechMs
    resetSegment()
    if (!frames.length || speechMs < options.minimumSpeechMs) return
    const wav = makeWavBlob(frames, sampleRate)
    safeCallback(onUtterance, wav, { speechMs })
  }

  const processFrame = (inputFrame) => {
    if (disposed || !inputFrame?.length) return
    if (!isEnabled()) {
      if (active) resetSegment()
      safeCallback(onLevel, 0)
      return
    }

    const frame = new Float32Array(inputFrame)
    const duration = frameMs(frame.length)
    const rms = calculateRms(frame)
    const level = clamp((rms - 0.001) / 0.055, 0, 1)
    safeCallback(onLevel, level, rms)
    const threshold = thresholdNow()
    const voiced = rms >= threshold

    if (!active) {
      // Estimate the room noise floor only while the signal is quiet. A slow
      // update avoids treating a syllable as the new ambient-noise baseline.
      if (!voiced) noiseFloor = (noiseFloor * 0.94) + (rms * 0.06)
      preRoll.push(frame)
      if (preRoll.length > maxPreRollFrames) preRoll.shift()

      if (voiced) {
        candidateFrames.push(frame)
        candidateSpeechMs += duration
        if (candidateSpeechMs >= options.startMs) {
          active = true
          segmentFrames = preRoll.slice()
          segmentSpeechMs = candidateSpeechMs
          segmentTotalMs = segmentFrames.reduce((total, item) => total + frameMs(item.length), 0)
          silenceMs = 0
          candidateFrames = []
          safeCallback(onSpeechStart, { rms, threshold })
        }
      } else {
        candidateFrames = []
        candidateSpeechMs = 0
      }
      return
    }

    segmentFrames.push(frame)
    segmentTotalMs += duration
    if (voiced) {
      segmentSpeechMs += duration
      silenceMs = 0
    } else {
      silenceMs += duration
    }

    if (silenceMs >= options.endSilenceMs || segmentTotalMs >= options.maximumUtteranceMs) {
      flush()
    }
  }

  return {
    processFrame,
    flush,
    reset: resetSegment,
    dispose() {
      if (disposed) return
      disposed = true
      // Closing Voice Mode is not an instruction to submit an unfinished phrase.
      resetSegment()
    },
    get isSpeaking() { return active },
    get threshold() { return thresholdNow() },
  }
}

/**
 * Opens the Voice Mode microphone once and performs local, continuous VAD.
 * It deliberately does not connect microphone audio to the speakers.
 */
export async function startVoiceActivityCapture({
  onSpeechStart,
  onUtterance,
  onLevel,
  onError,
  onStream,
  isEnabled = () => true,
} = {}) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot access a microphone for continuous Voice Mode.')
  }
  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (!AudioContextClass) throw new Error('Web Audio is unavailable in this browser.')

  let stream
  let audioContext
  let source
  let processor
  let silentGain
  let stopped = false

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: false,
    })
    if (!stream.getAudioTracks().some((track) => track.readyState === 'live')) {
      throw new Error('The selected microphone did not provide a live audio track.')
    }
    audioContext = new AudioContextClass()
    if (audioContext.state === 'suspended') await audioContext.resume()
    source = audioContext.createMediaStreamSource(stream)
    processor = audioContext.createScriptProcessor(2048, 1, 1)
    silentGain = audioContext.createGain()
    silentGain.gain.value = 0

    const detector = createVoiceActivityDetector({
      sampleRate: audioContext.sampleRate,
      onSpeechStart,
      onUtterance,
      onLevel,
      isEnabled,
    })

    processor.onaudioprocess = (event) => {
      if (stopped) return
      try {
        detector.processFrame(event.inputBuffer.getChannelData(0))
      } catch (error) {
        try { onError?.(error) } catch { /* non-fatal reporting */ }
      }
    }

    source.connect(processor)
    processor.connect(silentGain)
    silentGain.connect(audioContext.destination)
    onStream?.(stream)

    const stop = async () => {
      if (stopped) return
      stopped = true
      processor.onaudioprocess = null
      detector.dispose()
      try { source.disconnect() } catch { /* already disconnected */ }
      try { processor.disconnect() } catch { /* already disconnected */ }
      try { silentGain.disconnect() } catch { /* already disconnected */ }
      stream.getTracks().forEach((track) => track.stop())
      if (audioContext && audioContext.state !== 'closed') await audioContext.close().catch(() => {})
    }

    return {
      stream,
      audioContext,
      stop,
      setEnabled(enabled) {
        stream.getAudioTracks().forEach((track) => { track.enabled = Boolean(enabled) })
      },
    }
  } catch (error) {
    try { source?.disconnect() } catch { /* ignored */ }
    try { processor?.disconnect() } catch { /* ignored */ }
    try { silentGain?.disconnect() } catch { /* ignored */ }
    stream?.getTracks?.().forEach((track) => track.stop())
    if (audioContext && audioContext.state !== 'closed') await audioContext.close().catch(() => {})
    throw error
  }
}

export async function transcribeVoiceSegment(wavBlob, requestOrOptions = fetch) {
  // Keep the original injectable-request signature used by unit tests while
  // accepting the selected language from the live conversation controller.
  const request = typeof requestOrOptions === 'function'
    ? requestOrOptions
    : (requestOrOptions?.request || fetch)
  const language = typeof requestOrOptions === 'function'
    ? 'auto'
    : String(requestOrOptions?.language || 'auto')
  const url = new URL(NOVA_TRANSCRIBE_URL)
  if (language && language !== 'auto') url.searchParams.set('language', language)

  let response
  try {
    response = await request(url.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'audio/wav' },
      body: wavBlob,
    })
  } catch (error) {
    throw new Error('Could not reach NOVA’s backend for local speech recognition. Start api.py and keep Voicebox running.', { cause: error })
  }

  let payload
  try {
    payload = await response.json()
  } catch {
    payload = {}
  }
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Voicebox transcription failed (HTTP ${response.status}).`)
  }
  if (typeof payload.text !== 'string' || !payload.text.trim()) {
    throw new Error('No clear speech was recognised. NOVA will continue its previous response.')
  }
  return payload.text.trim()
}
