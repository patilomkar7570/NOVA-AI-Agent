/**
 * Browser-neutral Web Speech recognition capability detection.
 *
 * Auto mode prefers the browser's on-device SpeechRecognition language-pack
 * API and sets processLocally=true when available. If that local API is absent,
 * Auto can try the browser's standard recognizer next; some implementations may
 * send audio to a network service. If the browser recognizer is absent or fails,
 * NOVA uses Voicebox Whisper for STT. Voicebox is always the only TTS provider.
 */

const LOCAL_LOCALE_FALLBACKS = Object.freeze({
  en: ['en-US', 'en-IN', 'en-GB', 'en-AU'],
  de: ['de-DE', 'de-AT', 'de-CH'],
  fr: ['fr-FR', 'fr-CA'],
  es: ['es-ES', 'es-MX'],
  ja: ['ja-JP'],
  hi: ['hi-IN'],
  it: ['it-IT'],
  pt: ['pt-PT', 'pt-BR'],
  ko: ['ko-KR'],
})

function normalizeLocale(value) {
  const raw = String(value || '').trim().replaceAll('_', '-')
  if (!raw) return ''
  try {
    return Intl.getCanonicalLocales(raw)[0] || raw
  } catch {
    return raw
  }
}

function languageCode(value) {
  return normalizeLocale(value).split('-')[0].toLowerCase()
}

function unique(values) {
  return [...new Set(values.filter(Boolean))]
}

/** Return locale candidates; actual availability is checked by the browser. */
export function getBrowserOnDeviceRecognitionLocales(language, browserLocale = 'en-IN') {
  const selected = normalizeLocale(language)
  const preferred = selected && selected !== 'auto'
    ? selected
    : normalizeLocale(browserLocale) || 'en-in'
  const code = languageCode(preferred)
  return unique([preferred, ...(LOCAL_LOCALE_FALLBACKS[code] || [])])
}

/** Resolve the standard or vendor-prefixed Web Speech constructor. */
export function getBrowserSpeechRecognitionConstructor(browserWindow = globalThis.window) {
  return browserWindow?.SpeechRecognition || browserWindow?.webkitSpeechRecognition || null
}

/**
 * Check/install an on-device language pack without relying on a browser-name
 * sniff. This works wherever the browser implements the standard local API.
 */
export async function ensureBrowserOnDeviceRecognition(SpeechRecognition, locales) {
  if (typeof SpeechRecognition !== 'function') {
    return {
      available: false,
      reason: 'speech-recognition-unavailable',
      message: 'This browser does not expose SpeechRecognition.',
    }
  }

  if (typeof SpeechRecognition.available !== 'function' || typeof SpeechRecognition.install !== 'function') {
    return {
      available: false,
      reason: 'on-device-api-unavailable',
      message: 'This browser does not expose the on-device speech model API.',
    }
  }

  const candidates = unique(Array.isArray(locales) ? locales : [locales])
  if (!candidates.length) {
    return {
      available: false,
      reason: 'unsupported-language',
      message: 'No suitable speech-recognition language was selected.',
    }
  }

  const failures = []
  for (const locale of candidates) {
    const options = { langs: [locale], processLocally: true }
    try {
      const status = await SpeechRecognition.available(options)
      if (status === 'available') {
        return { available: true, locale, installedNow: false, processLocally: true }
      }

      if (status === 'downloadable' || status === 'downloading') {
        const installed = await SpeechRecognition.install(options)
        if (installed) {
          return { available: true, locale, installedNow: true, processLocally: true }
        }
        failures.push(`${locale}: install-failed`)
        continue
      }

      failures.push(`${locale}: ${status || 'unavailable'}`)
    } catch (error) {
      failures.push(`${locale}: ${error instanceof Error ? error.message : 'availability-check-failed'}`)
    }
  }

  return {
    available: false,
    reason: 'language-model-unavailable',
    localesTried: candidates,
    message: `No browser-local speech model is available for ${candidates.join(', ')}.`,
    details: failures,
  }
}

/** Build an instance with a consistent configuration for each mode. */
export function configureBrowserSpeechRecognition(recognition, { locale, onDevice = false } = {}) {
  if (!recognition) throw new TypeError('A SpeechRecognition instance is required.')
  recognition.lang = locale || 'en-US'
  recognition.continuous = true
  recognition.interimResults = true
  recognition.maxAlternatives = 1
  // Set only when strict local capability has already been verified.
  recognition.processLocally = Boolean(onDevice)
  return recognition
}
