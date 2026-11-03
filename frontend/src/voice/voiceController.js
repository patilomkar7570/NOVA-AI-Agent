const NOVA_API = 'http://127.0.0.1:8000'
const TARGET_SAMPLE_RATE = 16000
const MAX_RECORDING_SECONDS = 300

function reportNonFatalVoiceError(operation, error) {
  // Best-effort cleanup and visual feedback must not interrupt microphone I/O.
  if (import.meta.env.DEV) {
    console.debug(`[NOVA voice] ${operation} was non-fatal:`, error)
  }
}


function createVoiceLevelReporter(onLevel) {
  let smoothed = 0
  return (rms) => {
    // Use a speech-friendly noise gate and a nonlinear curve so ordinary
    // conversational volume is visible without making room noise dominate.
    const normalized = Math.max(0, Math.min(1, (rms - 0.0008) / 0.025))
    const target = Math.pow(normalized, 0.72)
    smoothed += (target - smoothed) * (target > smoothed ? 0.68 : 0.22)
    try {
      onLevel?.(Math.max(0, Math.min(1, smoothed)))
    } catch (error) {
      reportNonFatalVoiceError('Audio-level callback', error)
    }
  }
}

function downsampleAverage(input, inputRate, outputRate) {
  if (inputRate === outputRate) return input
  const ratio = inputRate / outputRate
  const outputLength = Math.floor(input.length / ratio)
  const output = new Float32Array(outputLength)

  for (let outIndex = 0; outIndex < outputLength; outIndex += 1) {
    const start = Math.floor(outIndex * ratio)
    const end = Math.min(Math.floor((outIndex + 1) * ratio), input.length)
    let sum = 0
    for (let index = start; index < end; index += 1) sum += input[index]
    output[outIndex] = sum / Math.max(1, end - start)
  }

  return output
}

function encodeMonoPcm16Wav(samples, sampleRate) {
  const bytesPerSample = 2
  const dataLength = samples.length * bytesPerSample
  const buffer = new ArrayBuffer(44 + dataLength)
  const view = new DataView(buffer)
  const writeAscii = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index))
    }
  }

  writeAscii(0, 'RIFF')
  view.setUint32(4, 36 + dataLength, true)
  writeAscii(8, 'WAVE')
  writeAscii(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * bytesPerSample, true)
  view.setUint16(32, bytesPerSample, true)
  view.setUint16(34, 16, true)
  writeAscii(36, 'data')
  view.setUint32(40, dataLength, true)

  let offset = 44
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]))
    const pcm = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    view.setInt16(offset, pcm, true)
    offset += bytesPerSample
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

async function requestMicrophoneStream() {
  try {
    // Do not require optional audio-processing/channel constraints. Let the
    // browser negotiate the default Windows input device.
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    if (!stream.getAudioTracks().some((track) => track.readyState === 'live')) {
      for (const track of stream.getTracks()) track.stop()
      throw new Error('The selected microphone did not provide a live audio track.')
    }
    return stream
  } catch (error) {
    if (error instanceof Error && error.message.includes('did not provide a live audio track')) {
      throw error
    }
    const name = error?.name || ''
    if (name === 'NotAllowedError' || name === 'SecurityError') {
      throw new Error('Microphone permission is blocked. Allow microphone access for NOVA in your browser and Windows privacy settings.')
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      throw new Error('No microphone was found. Connect or enable a microphone, then retry.')
    }
    if (name === 'NotReadableError' || name === 'AbortError') {
      throw new Error('Windows could not open the microphone. Check whether another app is holding the device, then retry.')
    }
    throw new Error(`Could not open the microphone${error?.message ? `: ${error.message}` : '.'}`)
  }
}

/**
 * Capture a temporary local copy while browser speech recognition is active.
 * The copy is retained only if online recognition fails or returns no words.
 * It is converted to mono 16 kHz PCM WAV for Voicebox's /captures endpoint.
 */
export async function startWavBackup({ onLevel } = {}) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot record a local audio backup.')
  }

  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (!AudioContextClass) throw new Error('Web Audio is unavailable in this browser.')

  const stream = await requestMicrophoneStream()

  let context
  let source
  let processor
  let silentGain
  let disposed = false
  let stopPromise = null
  const chunks = []
  const reportLevel = createVoiceLevelReporter(onLevel)
  let totalSamples = 0
  let captureLimitReached = false

  try {
    context = new AudioContextClass()
    await context.resume()
    const sourceRate = context.sampleRate
    const maxSamples = Math.floor(sourceRate * MAX_RECORDING_SECONDS)
    source = context.createMediaStreamSource(stream)
    processor = context.createScriptProcessor(4096, 1, 1)
    silentGain = context.createGain()
    silentGain.gain.value = 0

    processor.onaudioprocess = (event) => {
      if (disposed || captureLimitReached) return
      const frame = event.inputBuffer.getChannelData(0)
      if (typeof onLevel === 'function') {
        let energy = 0
        for (let index = 0; index < frame.length; index += 1) {
          const sample = frame[index]
          energy += sample * sample
        }
        reportLevel(Math.sqrt(energy / Math.max(1, frame.length)))
      }
      const remaining = maxSamples - totalSamples
      if (remaining <= 0) {
        captureLimitReached = true
        return
      }
      const copy = new Float32Array(frame.subarray(0, Math.min(frame.length, remaining)))
      chunks.push(copy)
      totalSamples += copy.length
      if (totalSamples >= maxSamples) captureLimitReached = true
    }

    source.connect(processor)
    processor.connect(silentGain)
    silentGain.connect(context.destination)

    const dispose = async () => {
      if (disposed) return
      disposed = true
      if (processor) processor.onaudioprocess = null
      try {
        source?.disconnect()
      } catch (error) {
        reportNonFatalVoiceError('Audio source disconnect', error)
      }
      try {
        processor?.disconnect()
      } catch (error) {
        reportNonFatalVoiceError('Audio processor disconnect', error)
      }
      try {
        silentGain?.disconnect()
      } catch (error) {
        reportNonFatalVoiceError('Silent gain disconnect', error)
      }
      for (const track of stream.getTracks()) track.stop()
      if (context && context.state !== 'closed') {
        try {
          await context.close()
        } catch (error) {
          reportNonFatalVoiceError('Audio context close', error)
        }
      }
    }

    return {
      stop() {
        if (stopPromise) return stopPromise
        stopPromise = (async () => {
          await dispose()
          const combined = new Float32Array(totalSamples)
          let offset = 0
          for (const frame of chunks) {
            combined.set(frame, offset)
            offset += frame.length
          }
          const resampled = downsampleAverage(combined, sourceRate, TARGET_SAMPLE_RATE)
          if (resampled.length < TARGET_SAMPLE_RATE * 0.15) {
            throw new Error('No usable microphone audio was captured. Speak for a little longer and retry.')
          }
          return encodeMonoPcm16Wav(resampled, TARGET_SAMPLE_RATE)
        })()
        return stopPromise
      },
      async abort() {
        chunks.length = 0
        totalSamples = 0
        await dispose()
      },
      get limitReached() {
        return captureLimitReached
      },
    }
  } catch (error) {
    for (const track of stream.getTracks()) track.stop()
    if (context && context.state !== 'closed') {
      try {
        await context.close()
      } catch (closeError) {
        reportNonFatalVoiceError('Audio context close after capture setup failed', closeError)
      }
    }
    throw error
  }
}


/**
 * Opens a microphone stream solely to measure live audio levels for NOVA's
 * waveform UI. Audio is analysed in memory and is never recorded or uploaded.
 */
export async function startMicLevelMonitor(onLevel) {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('This browser cannot access a microphone level meter.')
  }

  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (!AudioContextClass) throw new Error('Web Audio is unavailable in this browser.')

  const stream = await requestMicrophoneStream()

  let context
  let source
  let analyser
  let silentGain
  let frameId = 0
  let stopped = false
  let lastSampleAt = 0

  try {
    context = new AudioContextClass()
    await context.resume()
    source = context.createMediaStreamSource(stream)
    analyser = context.createAnalyser()
    analyser.fftSize = 1024
    analyser.smoothingTimeConstant = 0.78
    silentGain = context.createGain()
    silentGain.gain.value = 0
    source.connect(analyser)
    // Keep the analysis graph alive without monitoring microphone audio aloud.
    analyser.connect(silentGain)
    silentGain.connect(context.destination)
    const data = new Uint8Array(analyser.fftSize)
    const reportLevel = createVoiceLevelReporter(onLevel)

    const sample = (time) => {
      if (stopped) return
      frameId = window.requestAnimationFrame(sample)
      if (time - lastSampleAt < 42) return
      lastSampleAt = time
      analyser.getByteTimeDomainData(data)
      let energy = 0
      for (let index = 0; index < data.length; index += 1) {
        const value = (data[index] - 128) / 128
        energy += value * value
      }
      const rms = Math.sqrt(energy / data.length)
      reportLevel(rms)
    }

    frameId = window.requestAnimationFrame(sample)

    return {
      async stop() {
        if (stopped) return
        stopped = true
        if (frameId) window.cancelAnimationFrame(frameId)
        try {
          source?.disconnect()
        } catch (error) {
          reportNonFatalVoiceError('Microphone source disconnect', error)
        }
        try {
          analyser?.disconnect?.()
        } catch (error) {
          reportNonFatalVoiceError('Microphone analyser disconnect', error)
        }
        try {
          silentGain?.disconnect()
        } catch (error) {
          reportNonFatalVoiceError('Microphone silent-gain disconnect', error)
        }
        for (const track of stream.getTracks()) track.stop()
        if (context && context.state !== 'closed') {
          try {
            await context.close()
          } catch (error) {
            reportNonFatalVoiceError('Audio context close', error)
          }
        }
      },
    }
  } catch (error) {
    try { silentGain?.disconnect() } catch (closeError) {
      reportNonFatalVoiceError('Microphone silent-gain cleanup', closeError)
    }
    for (const track of stream.getTracks()) track.stop()
    if (context && context.state !== 'closed') {
      try {
        await context.close()
      } catch (closeError) {
        reportNonFatalVoiceError('Audio context close after monitor setup failed', closeError)
      }
    }
    throw error
  }
}

export async function transcribeWithVoicebox(wavBlob, language = 'auto') {
  let response
  try {
    const url = new URL(`${NOVA_API}/api/voice/transcribe`)
    const selectedLanguage = String(language || 'auto')
    if (selectedLanguage !== 'auto') url.searchParams.set('language', selectedLanguage)
    response = await fetch(url.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'audio/wav' },
      body: wavBlob,
    })
  } catch (error) {
    throw new Error('Could not reach NOVA’s backend. Start api.py and keep Voicebox open.', {
      cause: error,
    })
  }

  let payload
  try {
    payload = await response.json()
  } catch (error) {
    payload = {
      error: error instanceof Error
        ? `The backend returned an unreadable response: ${error.message}`
        : 'The backend returned an unreadable response.',
    }
  }

  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Local transcription failed (HTTP ${response.status}).`)
  }
  if (typeof payload.text !== 'string' || !payload.text.trim()) {
    throw new Error('Voicebox did not detect usable speech. Try speaking a little longer and more clearly.')
  }
  return payload
}
