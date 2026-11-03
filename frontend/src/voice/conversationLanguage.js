export const NOVA_CONVERSATION_LANGUAGES = Object.freeze([
  { code: 'auto', label: 'Automatic', locale: null, description: 'Detect the language you speak and follow it.' },
  { code: 'en', label: 'English', locale: 'en-IN', description: 'Listen and reply in English.' },
  { code: 'de', label: 'German', locale: 'de-DE', description: 'Auf Deutsch zuhören und antworten.' },
  { code: 'fr', label: 'French', locale: 'fr-FR', description: 'Écouter et répondre en français.' },
  { code: 'es', label: 'Spanish', locale: 'es-ES', description: 'Escuchar y responder en español.' },
  { code: 'ja', label: 'Japanese', locale: 'ja-JP', description: '日本語で聞き取り、回答します。' },
  { code: 'hi', label: 'Hindi', locale: 'hi-IN', description: 'हिंदी में सुनें और जवाब दें।' },
])

const VALID_CODES = new Set(NOVA_CONVERSATION_LANGUAGES.map((item) => item.code))

export function normalizeConversationLanguage(value, fallback = 'en') {
  const raw = String(value || '').trim().toLowerCase().replaceAll('_', '-')
  if (['automatic', 'detect', 'autodetect', 'auto-detect'].includes(raw)) return 'auto'
  const code = raw.split('-')[0]
  if (VALID_CODES.has(code)) return code
  return VALID_CODES.has(fallback) ? fallback : 'en'
}

export function getBrowserRecognitionLocale(language, browserLocale = 'en-IN') {
  const code = normalizeConversationLanguage(language)
  if (code === 'auto') {
    // Web Speech has no standard cross-language autodetect mode. Use the
    // browser locale as the best online hint; NOVA routes Auto to Whisper locally.
    return String(browserLocale || 'en-IN').replace('_', '-')
  }
  return NOVA_CONVERSATION_LANGUAGES.find((item) => item.code === code)?.locale || 'en-IN'
}


/** Best-effort language hint for speech output when the preference is Automatic.
 * Incoming audio itself is still transcribed by Whisper's own auto-detection.
 */
export function detectConversationLanguage(input, fallback = 'auto') {
  const text = String(input || '').trim().toLowerCase()
  if (!text) return fallback
  if (/[\u0900-\u097f]/.test(text)) return 'hi'
  if (/[\u3040-\u30ff]/.test(text)) return 'ja'
  const words = text.match(/[\p{L}']+/gu) || []
  const markers = {
    de: new Set(['der', 'die', 'das', 'und', 'ist', 'nicht', 'mit', 'für', 'ich', 'ein', 'eine', 'wir', 'aber', 'guten', 'morgen', 'danke', 'bitte']),
    fr: new Set(['le', 'la', 'les', 'des', 'et', 'est', 'pas', 'avec', 'pour', 'je', 'vous', 'nous', 'une', 'dans', 'mais', 'bonjour', 'merci', 'oui', 'non']),
    es: new Set(['el', 'los', 'las', 'y', 'es', 'no', 'con', 'para', 'yo', 'una', 'que', 'por', 'pero', 'hola', 'gracias', 'buenos', 'días', 'quiero']),
    en: new Set(['the', 'and', 'is', 'not', 'with', 'for', 'you', 'we', 'of', 'to', 'in', 'that', 'this', 'are', 'but', 'hello', 'thanks', 'please']),
  }
  const strong = {
    de: new Set(['guten', 'morgen', 'danke', 'bitte']),
    fr: new Set(['bonjour', 'merci', 'oui', 'non']),
    es: new Set(['hola', 'gracias']),
  }
  const scores = Object.fromEntries(Object.entries(markers).map(([code, set]) => [
    code, words.reduce((score, word) => score + (set.has(word) ? (strong[code]?.has(word) ? 2 : 1) : 0), 0),
  ]))
  const accents = {
    de: (text.match(/[äöüß]/g) || []).length,
    fr: (text.match(/[àâçéèêëîïôùûüÿœ]/g) || []).length,
    es: (text.match(/[áéíóúñ¿¡]/g) || []).length,
  }
  for (const [code, count] of Object.entries(accents)) scores[code] += count * 2
  const ranked = Object.entries(scores).sort((a, b) => b[1] - a[1])
  if (!ranked[0] || ranked[0][1] === 0) return fallback
  if (ranked[0][1] === ranked[1][1]) return fallback
  if (words.length < 4 && ranked[0][1] < 2) return fallback
  return ranked[0][0]
}


/**
 * Correct a common speech-recognition substitution of NOVA -> "Noah".
 *
 * This is deliberately context-limited: it only rewrites "Noah" when it is
 * clearly being used as the assistant's wake name (a standalone wake call,
 * a greeting, or an initial direct-address command). Mentions such as
 * "Who was Noah?" and "I spoke to Noah yesterday" are left untouched.
 */
export function normalizeNOVAAssistantNameTranscript(input) {
  const text = String(input ?? '')
  if (!text) return text

  // A wake phrase followed by the ASR substitution, e.g. "Hi Noah" or
  // "Good morning, Noah". Preserve the original greeting and punctuation.
  const greetingPattern = /^(\s*(?:hi|hii|hello|hey|yo|okay|ok|good\s+morning|good\s+afternoon|good\s+evening|are\s+you\s+there|wake\s+up|listen)\b[\s,]*)noah\b/i
  if (greetingPattern.test(text)) {
    return text.replace(greetingPattern, (_match, prefix) => `${prefix}NOVA`)
  }

  // The assistant's name used as the first word of a direct-address request.
  // Requiring punctuation or a clear instruction/question starter avoids
  // changing ordinary statements about a person named Noah.
  const directAddressPattern = /^(\s*)noah(?=$|\s*[,!?.:;—–-]|\s+(?:please|can|could|would|will|what|who|where|when|why|how|tell|show|explain|find|search|open|check|look|read|summarize|help|give|make|write|start|stop|play|turn)\b)/i
  if (directAddressPattern.test(text)) {
    return text.replace(directAddressPattern, (_match, prefix) => `${prefix}NOVA`)
  }

  // A final vocative after a comma is also a common dictation form.
  const trailingVocativePattern = /(,\s*)noah(\s*[.!?]?)$/i
  if (trailingVocativePattern.test(text)) {
    return text.replace(trailingVocativePattern, (_match, separator, punctuation) => `${separator}NOVA${punctuation}`)
  }

  return text
}
