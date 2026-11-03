const DEFAULT_SPEAK_URL = 'http://127.0.0.1:8000/api/voice/speak'

export function splitSpeechIntoChunks(input, maxChunkLength = 360) {
  const text = String(input || '')
  const chunks = []
  let cursor = 0
  const boundary = /[.!?]+["'”’)}\]]*(?=\s|$)/g
  let match

  while ((match = boundary.exec(text)) !== null) {
    const end = match.index + match[0].length
    const chunk = text.slice(cursor, end).trim()
    if (chunk) chunks.push(chunk)
    cursor = end
  }

  let remainder = text.slice(cursor).trim()
  while (remainder.length > maxChunkLength) {
    let splitAt = remainder.lastIndexOf(' ', maxChunkLength)
    if (splitAt < Math.floor(maxChunkLength * 0.55)) splitAt = maxChunkLength
    const chunk = remainder.slice(0, splitAt).trim()
    if (!chunk) break
    chunks.push(chunk)
    remainder = remainder.slice(splitAt).trim()
  }
  if (remainder) chunks.push(remainder)
  return chunks
}

export function createVoicePlaybackQueue({
  audioContext,
  profileId = null,
  language = 'auto',
  playbackRate = 1,
  speakUrl = DEFAULT_SPEAK_URL,
  request = (...args) => fetch(...args),
  onState = () => {},
  onError = () => {},
} = {}) {
  if (!audioContext) throw new Error('An active AudioContext is required for NOVA voice playback.')

  let textBuffer = ''
  let pendingText = []
  let preparedAudio = []
  let controllers = new Set()
  let generationActive = false
  let playbackActive = false
  let currentSource = null
  let currentBuffer = null
  let currentOffset = 0
  let currentStartedAt = 0
  let paused = false
  let started = false
  let inputFinished = false
  let cancelled = false
  let settled = false
  const safePlaybackRate = Math.max(0.8, Math.min(1.25, Number(playbackRate) || 1))
  let resolveCompletion
  let rejectCompletion
  let completion = null

  const completionPromise = () => {
    if (!completion) {
      completion = new Promise((resolve, reject) => {
        resolveCompletion = resolve
        rejectCompletion = reject
      })
    }
    return completion
  }

  const reportError = (error) => {
    try { onError(error) } catch { /* UI callbacks must not break the queue */ }
  }

  const setState = (state) => {
    try { onState(state) } catch { /* UI callbacks must not break the queue */ }
  }

  const complete = () => {
    if (settled || cancelled || paused || !inputFinished || generationActive || playbackActive || currentBuffer) return
    if (pendingText.length || preparedAudio.length || textBuffer.trim()) return
    settled = true
    setState('complete')
    resolveCompletion?.()
  }

  const startBuffer = (buffer, offset = 0) => {
    if (cancelled || paused || !buffer) return
    const safeOffset = Math.max(0, Math.min(offset, Math.max(0, buffer.duration - 0.015)))
    let source
    try {
      source = audioContext.createBufferSource()
      source.buffer = buffer
      if (source.playbackRate) source.playbackRate.value = safePlaybackRate
      source.connect(audioContext.destination)
      currentBuffer = buffer
      currentOffset = safeOffset
      currentStartedAt = audioContext.currentTime
      currentSource = source
      playbackActive = true
      setState('speaking')
      source.onended = () => {
        // Ignore the onended event caused by a deliberate pause/cancel.
        if (currentSource !== source) return
        currentSource = null
        currentBuffer = null
        currentOffset = 0
        playbackActive = false
        if (cancelled || paused) return
        playNext()
      }
      source.start(0, safeOffset)
    } catch (error) {
      playbackActive = false
      currentSource = null
      currentBuffer = null
      reportError(error)
      fail(error)
    }
  }

  const playNext = () => {
    if (cancelled || paused || playbackActive) {
      complete()
      return
    }

    if (currentBuffer) {
      startBuffer(currentBuffer, currentOffset)
      return
    }

    if (!preparedAudio.length) {
      complete()
      return
    }
    startBuffer(preparedAudio.shift(), 0)
  }

  const stopCurrentSource = () => {
    const source = currentSource
    currentSource = null
    if (!source) return
    source.onended = null
    try { source.stop() } catch { /* source may already have ended */ }
    try { source.disconnect() } catch { /* ignored */ }
  }

  const fail = (error) => {
    if (settled || cancelled) return
    cancelled = true
    for (const controller of controllers) controller.abort()
    controllers.clear()
    stopCurrentSource()
    playbackActive = false
    generationActive = false
    currentBuffer = null
    currentOffset = 0
    pendingText = []
    preparedAudio = []
    settled = true
    setState('cancelled')
    rejectCompletion?.(error)
  }

  async function generatePending() {
    if (generationActive || cancelled) return
    generationActive = true
    try {
      while (pendingText.length && !cancelled) {
        const text = pendingText.shift()
        const controller = new AbortController()
        controllers.add(controller)
        if (!playbackActive && !paused) setState('generating')
        let response
        try {
          try {
            response = await request(speakUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'Accept': 'audio/*, application/octet-stream' },
              body: JSON.stringify({
                text,
                ...(profileId ? { profile_id: String(profileId) } : {}),
                ...(language && String(language) !== 'auto' ? { language: String(language) } : {}),
              }),
              signal: controller.signal,
            })
          } catch (error) {
            if (error?.name === 'AbortError') throw error
            const detail = error instanceof Error && error.message ? ` (${error.message})` : ''
            throw new Error(`NOVA could not reach its Voicebox speech endpoint at ${speakUrl}. Make sure api.py is running and connected to Voicebox.${detail}`, { cause: error })
          }
        } finally {
          controllers.delete(controller)
        }
        if (cancelled) return
        if (!response?.ok) {
          let detail = `Voicebox speech generation failed (HTTP ${response?.status ?? 'unknown'}).`
          try {
            const payload = await response.json()
            detail = payload.error || payload.detail || detail
          } catch { /* keep generic HTTP error */ }
          throw new Error(detail)
        }
        const responseContentType = String(response.headers?.get?.('content-type') || '').split(';', 1)[0].trim().toLowerCase()
        if (responseContentType && !responseContentType.startsWith('audio/') && responseContentType !== 'application/octet-stream') {
          throw new Error(`NOVA expected an audio file from Voicebox but received ${responseContentType}. Check the /api/voice/speak response; an SVG or HTML response cannot be played as speech.`)
        }
        const bytes = await response.arrayBuffer()
        if (cancelled) return
        if (!bytes?.byteLength) throw new Error('Voicebox returned an empty audio file.')
        if (audioContext.state === 'suspended') await audioContext.resume()
        const audio = await audioContext.decodeAudioData(bytes.slice(0))
        if (cancelled) return
        preparedAudio.push(audio)
        if (!paused) playNext()
      }
    } catch (error) {
      if (error?.name !== 'AbortError' && !cancelled) {
        reportError(error)
        fail(error)
      }
    } finally {
      generationActive = false
      if (!cancelled && pendingText.length) void generatePending()
      else complete()
    }
  }

  const appendText = (delta) => {
    if (cancelled || inputFinished || settled) return
    textBuffer += String(delta || '')
    const boundary = /[.!?]+["'”’)}\]]*(?=\s|$)/g
    let lastEnd = 0
    let match
    while ((match = boundary.exec(textBuffer)) !== null) lastEnd = match.index + match[0].length
    if (lastEnd > 0) {
      const ready = splitSpeechIntoChunks(textBuffer.slice(0, lastEnd))
      if (ready.length) pendingText.push(...ready)
      textBuffer = textBuffer.slice(lastEnd)
    }
    while (textBuffer.trim().length > 360) {
      const splitAt = textBuffer.lastIndexOf(' ', 360)
      if (splitAt < 180) break
      pendingText.push(textBuffer.slice(0, splitAt).trim())
      textBuffer = textBuffer.slice(splitAt)
    }
    if (pendingText.length) void generatePending()
  }

  const finishInput = () => {
    if (cancelled || inputFinished) return completionPromise()
    inputFinished = true
    const last = textBuffer.trim()
    if (last) pendingText.push(last)
    textBuffer = ''
    if (pendingText.length) void generatePending()
    else complete()
    return completionPromise()
  }

  const startStreaming = () => {
    if (started) return completionPromise()
    started = true
    completionPromise()
    return completion
  }

  const start = (text) => {
    startStreaming()
    appendText(String(text || ''))
    return finishInput()
  }

  const pause = () => {
    if (cancelled || settled || paused) return false
    paused = true
    if (currentSource && currentBuffer) {
      const elapsed = Math.max(0, audioContext.currentTime - currentStartedAt)
      currentOffset = Math.min(currentBuffer.duration, currentOffset + elapsed * safePlaybackRate)
      stopCurrentSource()
      playbackActive = false
    }
    setState('paused')
    return true
  }

  const resume = () => {
    if (cancelled || settled || !paused) return false
    paused = false
    if (audioContext.state === 'suspended') {
      void audioContext.resume().catch((error) => reportError(error))
    }
    if (currentBuffer) startBuffer(currentBuffer, currentOffset)
    else if (preparedAudio.length) playNext()
    else if (generationActive || pendingText.length) setState('generating')
    else complete()
    return true
  }

  const cancel = () => {
    if (cancelled || settled) return
    cancelled = true
    paused = false
    inputFinished = true
    for (const controller of controllers) controller.abort()
    controllers.clear()
    stopCurrentSource()
    playbackActive = false
    currentBuffer = null
    currentOffset = 0
    pendingText = []
    preparedAudio = []
    textBuffer = ''
    settled = true
    setState('cancelled')
    resolveCompletion?.()
  }

  return {
    start,
    startStreaming,
    appendText,
    finishInput,
    pause,
    resume,
    cancel,
    dispose: cancel,
    isPlaying: () => playbackActive,
    isPaused: () => paused,
    hasPendingAudio: () => Boolean(currentBuffer || currentSource || preparedAudio.length || pendingText.length || generationActive || textBuffer.trim()),
  }
}
