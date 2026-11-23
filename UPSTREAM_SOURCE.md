# Third-Party Notices & Open Source Components

This project integrates open-source components under permissive licenses (MIT and Apache-2.0). See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) and [LICENSES/third-party/](LICENSES/third-party/) for full legal texts.

## Third-Party Components & Attributions

1. **Celestial Day/Night Theme Switch (`hard-goose-47`)**
   - **Source:** [Uiverse.io hard-goose-47](https://uiverse.io/00Kubi/hard-goose-47)
   - **Author:** 00Kubi (Jakub Grzybek)
   - **Origin:** Variation of Galahhad's switch
   - **License:** MIT (`LICENSES/third-party/HARD-GOOSE-47-MIT.txt`)
   - **Usage:** Operational Voice Menu theme switch (`nova-voice-room-header`), featuring animated sun/moon, starry sky, shooting stars, meteor, aurora, and comets.

2. **Day/Night Theme Changer Card (`young-dingo-21`)**
   - **Source:** [Uiverse.io young-dingo-21](https://uiverse.io/witer33/young-dingo-21)
   - **Author:** witer33
   - **License:** MIT (`LICENSES/third-party/YOUNG-DINGO-21-MIT.txt`)
   - **Usage:** Settings modal Appearance section (`theme-changer-container`). Centered card featuring smooth celestial gradient transitions and working Light/Dark mode buttons, positioned directly below the Match System Theme auto button.

3. **Original Day/Night Switch Base (`strong-squid-82`)**
   - **Source:** [Uiverse.io strong-squid-82](https://uiverse.io/Galahhad/strong-squid-82)
   - **Author:** Galahhad
   - **License:** MIT (`LICENSES/third-party/STRONG-SQUID-82-MIT.txt`)
   - **Usage:** Foundation design for the celestial toggle switch.

4. **Capybara Loading Element (`kind-snail-5`)**
   - **Source:** [Uiverse.io kind-snail-5](https://uiverse.io/Novaxlo/kind-snail-5)
   - **Author:** Novaxlo
   - **License:** MIT (`LICENSES/third-party/KIND-SNAIL-5-CAPYBARA-MIT.txt`)
   - **Usage:** Animated strolling capybara loader mounted along the top ridge of the prompt box (`.task-box`) while prompt response generation is active.

5. **Mercury Orb / VoiceOrbs**
   - **Source:** [amunozdev/voiceorbs](https://github.com/amunozdev/voiceorbs)
   - **Author:** Alexis Munoz
   - **License:** MIT (`LICENSES/VOICEORBS-MIT.txt`)
   - **Usage:** Interactive 3D voice activity indicator in NOVA Voice Mode.

6. **Paper Shaders**
   - **Source:** [paper-design/shaders](https://github.com/paper-design/shaders)
   - **License:** Apache-2.0 (`LICENSES/PAPER-SHADERS-APACHE-2.0.txt` and `LICENSES/PAPER-SHADERS-NOTICE.txt`)
   - **Usage:** WebGL shader pipelines for background atmospheric canvas.


## NOVA Integration Architecture
- The dictation capture and NOVA API CORS changes are NOVA integration code.
- Audio contract remains mono 16 kHz PCM WAV to NOVA's API, then multipart WAV to Voicebox `/captures`.

