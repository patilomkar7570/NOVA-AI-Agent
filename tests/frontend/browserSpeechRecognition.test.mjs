import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getBrowserOnDeviceRecognitionLocales,
  getBrowserSpeechRecognitionConstructor,
  ensureBrowserOnDeviceRecognition,
  configureBrowserSpeechRecognition,
} from '../../frontend/src/voice/browserSpeechRecognition.js'

test('maps English India to preferred locale plus compatible fallbacks', () => {
  assert.deepEqual(
    getBrowserOnDeviceRecognitionLocales('en', 'en-IN'),
    ['en', 'en-US', 'en-IN', 'en-GB', 'en-AU'],
  )
})

test('uses browser locale when conversation language is automatic', () => {
  assert.deepEqual(
    getBrowserOnDeviceRecognitionLocales('auto', 'de-DE'),
    ['de-DE', 'de-AT', 'de-CH'],
  )
})

test('resolves standard and WebKit-prefixed constructors without browser sniffing', () => {
  class StandardRecognition {}
  class WebkitRecognition {}
  assert.equal(getBrowserSpeechRecognitionConstructor({ SpeechRecognition: StandardRecognition }), StandardRecognition)
  assert.equal(getBrowserSpeechRecognitionConstructor({ webkitSpeechRecognition: WebkitRecognition }), WebkitRecognition)
  assert.equal(getBrowserSpeechRecognitionConstructor({}), null)
})

test('accepts an installed on-device language pack', async () => {
  class MockRecognition {}
  MockRecognition.available = async (options) => {
    assert.deepEqual(options, { langs: ['en-US'], processLocally: true })
    return 'available'
  }
  MockRecognition.install = async () => { throw new Error('install should not run') }
  assert.deepEqual(await ensureBrowserOnDeviceRecognition(MockRecognition, ['en-US']), {
    available: true, locale: 'en-US', installedNow: false, processLocally: true,
  })
})

test('tries later locale fallbacks when the first local model is unavailable', async () => {
  class MockRecognition {}
  const tried = []
  MockRecognition.available = async ({ langs }) => {
    tried.push(langs[0])
    return langs[0] === 'en-US' ? 'available' : 'unavailable'
  }
  MockRecognition.install = async () => false
  const result = await ensureBrowserOnDeviceRecognition(MockRecognition, ['en-IN', 'en-US'])
  assert.equal(result.available, true)
  assert.equal(result.locale, 'en-US')
  assert.deepEqual(tried, ['en-IN', 'en-US'])
})

test('installs a downloadable local model', async () => {
  class MockRecognition {}
  let installed = false
  MockRecognition.available = async () => installed ? 'available' : 'downloadable'
  MockRecognition.install = async () => { installed = true; return true }
  assert.deepEqual(await ensureBrowserOnDeviceRecognition(MockRecognition, ['en-US']), {
    available: true, locale: 'en-US', installedNow: true, processLocally: true,
  })
})

test('reports missing local-model API so Auto can try regular recognition next', async () => {
  class CloudOnlyRecognition {}
  const result = await ensureBrowserOnDeviceRecognition(CloudOnlyRecognition, ['en-US'])
  assert.equal(result.available, false)
  assert.equal(result.reason, 'on-device-api-unavailable')
})

test('configures online mode without forcing local processing', () => {
  const recognition = {}
  configureBrowserSpeechRecognition(recognition, { locale: 'en-IN', onDevice: false })
  assert.equal(recognition.lang, 'en-IN')
  assert.equal(recognition.continuous, true)
  assert.equal(recognition.interimResults, true)
  assert.equal(recognition.processLocally, false)
})
