# Third-Party Software Notices and Information

This project, **NOVA**, incorporates open-source code, assets, and components from third-party projects. This document provides clear attribution, source links, and license terms in full compliance with all upstream open-source licenses.

---

## Legal & Compliance Summary

### Permissive Licensing (MIT & Apache-2.0)
The third-party components listed below are distributed under permissive licenses (**MIT License** and **Apache License, Version 2.0**):
- **Commercial & Non-Commercial Use:** You are legally permitted to use, modify, merge, publish, and distribute the borrowed code.
- **Notice Preservation:** Both the MIT and Apache-2.0 licenses mandate that original copyright notices, permission notices, and disclaimers be retained in the distribution. This file and the documents within the `LICENSES/` folder satisfy this requirement.
- **License Compatibility:** Under open-source law, incorporating MIT-licensed and Apache-2.0-licensed components into NOVA (which utilizes the PolyForm Noncommercial License 1.0.0 for its proprietary codebase) is fully compliant:
  - The third-party components remain governed by their respective permissive licenses.
  - NOVA's proprietary application logic is governed by PolyForm Noncommercial 1.0.0.
  - Users are free to inspect, extract, and use the third-party components under their original MIT/Apache terms.

---

## Inventory of Third-Party Components

| Component / Library | Author / Copyright Holder | License | Upstream Link | Integration Location |
| :--- | :--- | :--- | :--- | :--- |
| **hard-goose-47** | Jakub Grzybek (`00Kubi`) | **MIT** | [Uiverse.io](https://uiverse.io/00Kubi/hard-goose-47) | Voice room operational header theme toggle (`frontend/src/App.jsx`, `frontend/src/App.css`) |
| **young-dingo-21** | `witer33` | **MIT** | [Uiverse.io](https://uiverse.io/witer33/young-dingo-21) | Settings Appearance theme changer card (`frontend/src/App.jsx`, `frontend/src/App.css`) |
| **strong-squid-82** | `Galahhad` | **MIT** | [Uiverse.io](https://uiverse.io/Galahhad/strong-squid-82) | Upstream base design for celestial day/night toggle (`frontend/src/App.css`) |
| **kind-snail-5** | `Novaxlo` | **MIT** | [Uiverse.io](https://uiverse.io/Novaxlo/kind-snail-5) | Capybara loader walking atop prompt bar during response streaming (`frontend/src/components/loader/CapybaraLoader.jsx`, `frontend/src/components/loader/CapybaraLoader.css`) |
| **VoiceOrbs (Mercury Orb)** | Alexis Munoz | **MIT** | [GitHub](https://github.com/amunozdev/voiceorbs) | Voice activity orb visualization (`frontend/src/components/voiceorbs/`) |
| **Paper Shaders** | Paper Design | **Apache-2.0** | [GitHub](https://github.com/paper-design/shaders) | Background atmospheric shader canvas (`frontend/src/components/canvas/`) |
| **Velora** | Velora AI Contributors | **MIT** | Upstream core | Core architecture components (`LICENSES/LICENSE-VELORA.txt`) |

---

## Complete Third-Party License Texts

### 1. Uiverse.io UI Components (MIT License)

#### A. hard-goose-47 (Celestial Day/Night Theme Switch)
```text
MIT License

Copyright (c) 2026 Jakub Grzybek (00Kubi)
Component: "hard-goose-47" (Celestial Day/Night Weather Theme Switch)
Source URL: https://uiverse.io/00Kubi/hard-goose-47

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

#### B. young-dingo-21 (Day/Night Theme Changer Card)
```text
MIT License

Copyright (c) 2026 witer33
Component: "young-dingo-21" (Day and Night Phone Card Theme Switcher)
Source URL: https://uiverse.io/witer33/young-dingo-21

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

#### C. strong-squid-82 (Original Day/Night Toggle Switch)
```text
MIT License

Copyright (c) 2026 Galahhad
Component: "strong-squid-82" (Day/Night Theme Switch)
Source URL: https://uiverse.io/Galahhad/strong-squid-82

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

#### D. kind-snail-5 (Capybara Loading)
```text
MIT License

Copyright (c) Novaxlo (Novaxlo)
Component: "kind-snail-5" (Capybara Loading)
Source URL: https://uiverse.io/Novaxlo/kind-snail-5

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

### 2. VoiceOrbs (MIT License)
```text
MIT License

Copyright (c) 2026 Alexis Munoz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

### 3. Paper Shaders (Apache License 2.0)
See [LICENSES/PAPER-SHADERS-APACHE-2.0.txt](LICENSES/PAPER-SHADERS-APACHE-2.0.txt) and [LICENSES/PAPER-SHADERS-NOTICE.txt](LICENSES/PAPER-SHADERS-NOTICE.txt) for full Apache-2.0 text and attribution notice.

---

### 4. Velora Core (MIT License)
See [LICENSES/LICENSE-VELORA.txt](LICENSES/LICENSE-VELORA.txt) for full license text.
