import test from 'node:test'
import assert from 'node:assert/strict'
import {
  NOVA_CONVERSATION_LANGUAGES,
  normalizeConversationLanguage,
  getBrowserRecognitionLocale,
  detectConversationLanguage,
  normalizeNOVAAssistantNameTranscript,
} from '../../frontend/src/voice/conversationLanguage.js'

test('offers Automatic plus the six requested languages', () => {
  assert.deepEqual(NOVA_CONVERSATION_LANGUAGES.map((item) => item.code), ['auto', 'en', 'de', 'fr', 'es', 'ja', 'hi'])
})

test('normalises language tags and rejects unknown values safely', () => {
  assert.equal(normalizeConversationLanguage('hi-IN'), 'hi')
  assert.equal(normalizeConversationLanguage('de_DE'), 'de')
  assert.equal(normalizeConversationLanguage('automatic'), 'auto')
  assert.equal(normalizeConversationLanguage('xx'), 'en')
})

test('maps selected languages to browser locales', () => {
  assert.equal(getBrowserRecognitionLocale('hi'), 'hi-IN')
  assert.equal(getBrowserRecognitionLocale('ja'), 'ja-JP')
  assert.equal(getBrowserRecognitionLocale('auto', 'de-DE'), 'de-DE')
})


test('detects script languages and common Latin-script replies for Auto TTS', () => {
  assert.equal(detectConversationLanguage('नमस्ते, आप कैसे हैं?'), 'hi')
  assert.equal(detectConversationLanguage('こんにちは、元気ですか？'), 'ja')
  assert.equal(detectConversationLanguage('Bonjour, merci beaucoup.'), 'fr')
  assert.equal(detectConversationLanguage('Hola, gracias por venir.'), 'es')
  assert.equal(detectConversationLanguage('Guten Morgen, danke.'), 'de')
  assert.equal(detectConversationLanguage('An ambiguous phrase', 'auto'), 'auto')
})


test('corrects Noah only when it is being used as the spoken NOVA assistant name', () => {
  assert.equal(normalizeNOVAAssistantNameTranscript('Noah'), 'NOVA')
  assert.equal(normalizeNOVAAssistantNameTranscript('Hey Noah, open the browser.'), 'Hey NOVA, open the browser.')
  assert.equal(normalizeNOVAAssistantNameTranscript('Noah can you explain this?'), 'NOVA can you explain this?')
  assert.equal(normalizeNOVAAssistantNameTranscript('I spoke to Noah yesterday.'), 'I spoke to Noah yesterday.')
})
