# Third-party notices retained by this patch

This patch preserves the existing Mercury Orb integration; it does not modify the component.

- VoiceOrbs: https://github.com/amunozdev/voiceorbs — MIT. See `LICENSES/VOICEORBS-MIT.txt`.
- Paper Shaders: https://github.com/paper-design/shaders — Apache-2.0. See `LICENSES/PAPER-SHADERS-APACHE-2.0.txt` and `LICENSES/PAPER-SHADERS-NOTICE.txt`.

The dictation capture and NOVA API CORS changes in this patch are NOVA integration code. The audio contract remains mono 16 kHz PCM WAV to NOVA's API, then multipart WAV to Voicebox `/captures`.
