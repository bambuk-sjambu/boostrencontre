"""Tinder anti-detection layer.

T1-B superseded on 2026-04-23 → T1-A (VPN France). Reason: Tinder Web from
Cambodia IP only offers Google auth, no phone signup path. Switched to
ProtonVPN FR so Tinder serves the phone-first flow. Fingerprint stack now
aligns to France (locale fr-FR, timezone Europe/Paris).

Per security + research reviews:
- Use `patchright.async_api` instead of `playwright.async_api` (drop-in)
- Avoid `--disable-blink-features=AutomationControlled` flag (patchright handles)
- Cover 2024-2026 fingerprint surfaces that `playwright-stealth` misses

Rotate STEALTH_VERSION whenever the init script content changes so bans can be
git-bisect'd to a specific revision.
"""

STEALTH_VERSION = "2026.04.23-fr"

TINDER_LOCALE = "fr-FR"
TINDER_TIMEZONE = "Europe/Paris"
TINDER_LANGUAGES = ["fr-FR", "fr", "en-US", "en"]
TINDER_VIEWPORT = {"width": 1440, "height": 900}


def get_launch_kwargs() -> dict:
    """Launch kwargs for `chromium.launch_persistent_context`.

    Intentionally omits `--disable-blink-features=AutomationControlled` —
    patchright patches the underlying surfaces at CDP level, and the flag
    itself is a fingerprint signal per public bypass research (2024-2025).
    """
    return {
        "locale": TINDER_LOCALE,
        "timezone_id": TINDER_TIMEZONE,
        "viewport": TINDER_VIEWPORT,
        "args": [
            "--no-first-run",
            "--no-default-browser-check",
            "--window-position=0,1400",
            "--window-size=1440,900",
        ],
    }


def get_init_script() -> str:
    """Return the JS init script injected before any Tinder page JS runs.

    Covers fingerprint surfaces flagged by security review:
    - navigator.webdriver (belt-and-suspenders with patchright)
    - navigator.plugins: realistic PDF viewer entries
    - navigator.languages: en-US primary
    - navigator.hardwareConcurrency + deviceMemory: realistic consumer values
    - screen.colorDepth / pixelDepth alignment
    - WebGL vendor/renderer spoof to consumer GPU
    - Canvas.toDataURL deterministic noise (NOT random — random is itself a signal)
    - AudioContext fingerprint noise
    - mediaDevices.enumerateDevices populated stub
    - speechSynthesis.getVoices populated stub
    - Function.prototype.toString spoof for patched getters (hides `[object Object]`
      vs native `[native code]` leak)
    - iframe contentWindow re-patching (classic bypass)
    - chrome.runtime populated stub
    - Permissions.query returns real Notification state
    - Client Hints (Sec-CH-UA) — browser-level, not patchable here; patchright covers

    Missing (requires patchright or OS-level): TLS JA4, HTTP/2 SETTINGS frame order,
    Client Hints header alignment with UA string.
    """
    return r"""
(() => {
  'use strict';

  // --- Function.prototype.toString spoof (hide overrides) ---
  const nativeToString = Function.prototype.toString;
  const toStringMap = new WeakMap();
  Function.prototype.toString = function() {
    if (toStringMap.has(this)) {
      return toStringMap.get(this);
    }
    return nativeToString.call(this);
  };
  const registerNative = (fn, nativeName) => {
    toStringMap.set(fn, 'function ' + nativeName + '() { [native code] }');
    return fn;
  };

  // --- navigator.webdriver ---
  try {
    Object.defineProperty(Navigator.prototype, 'webdriver', {
      get: registerNative(function webdriver() { return undefined; }, 'webdriver'),
      configurable: true,
    });
  } catch (e) {}

  // --- Chromium CDC variable cleanup ---
  try {
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
  } catch (e) {}

  // --- navigator.plugins (realistic Chrome internal PDF viewers) ---
  // Build a PROPER PluginArray (not a hacked Array) so that
  // Object.prototype.toString.call(navigator.plugins) === '[object PluginArray]'
  // and each item passes `instanceof Plugin`.
  try {
    const pluginsData = [
      { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
      { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
      { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
      { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
      { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
    ];

    const buildPlugin = (data) => {
      const plugin = Object.create(Plugin.prototype);
      Object.defineProperty(plugin, 'name', { value: data.name, enumerable: true });
      Object.defineProperty(plugin, 'filename', { value: data.filename, enumerable: true });
      Object.defineProperty(plugin, 'description', { value: data.description, enumerable: true });
      Object.defineProperty(plugin, 'length', { value: 0, enumerable: true });
      plugin.item = registerNative(function item() { return null; }, 'item');
      plugin.namedItem = registerNative(function namedItem() { return null; }, 'namedItem');
      return plugin;
    };

    const plist = Object.create(PluginArray.prototype);
    const builtPlugins = pluginsData.map(buildPlugin);
    builtPlugins.forEach((p, i) => {
      Object.defineProperty(plist, i, { value: p, enumerable: true });
      Object.defineProperty(plist, p.name, { value: p, enumerable: false });
    });
    Object.defineProperty(plist, 'length', { value: builtPlugins.length, enumerable: false });
    plist.item = registerNative(function item(i) { return plist[i] || null; }, 'item');
    plist.namedItem = registerNative(function namedItem(n) { return plist[n] || null; }, 'namedItem');
    plist.refresh = registerNative(function refresh() {}, 'refresh');

    Object.defineProperty(Navigator.prototype, 'plugins', {
      get: registerNative(function plugins() { return plist; }, 'plugins'),
      configurable: true,
    });
  } catch (e) {}

  // --- navigator.languages ---
  try {
    Object.defineProperty(Navigator.prototype, 'languages', {
      get: registerNative(function languages() {
        return ['fr-FR', 'fr', 'en-US', 'en'];
      }, 'languages'),
      configurable: true,
    });
  } catch (e) {}

  // --- navigator.hardwareConcurrency (8 cores = modern laptop) ---
  try {
    Object.defineProperty(Navigator.prototype, 'hardwareConcurrency', {
      get: registerNative(function hardwareConcurrency() { return 8; }, 'hardwareConcurrency'),
      configurable: true,
    });
  } catch (e) {}

  // --- navigator.deviceMemory (8 GB) ---
  try {
    Object.defineProperty(Navigator.prototype, 'deviceMemory', {
      get: registerNative(function deviceMemory() { return 8; }, 'deviceMemory'),
      configurable: true,
    });
  } catch (e) {}

  // --- screen color/pixel depth ---
  try {
    Object.defineProperty(Screen.prototype, 'colorDepth', {
      get: registerNative(function colorDepth() { return 24; }, 'colorDepth'),
      configurable: true,
    });
    Object.defineProperty(Screen.prototype, 'pixelDepth', {
      get: registerNative(function pixelDepth() { return 24; }, 'pixelDepth'),
      configurable: true,
    });
  } catch (e) {}

  // --- WebGL vendor + renderer (consumer Intel GPU) ---
  try {
    const getParameterOrig = WebGLRenderingContext.prototype.getParameter;
    const webglSpoof = registerNative(function getParameter(param) {
      // UNMASKED_VENDOR_WEBGL = 37445, UNMASKED_RENDERER_WEBGL = 37446
      if (param === 37445) return 'Intel Inc.';
      if (param === 37446) return 'Intel Iris OpenGL Engine';
      return getParameterOrig.call(this, param);
    }, 'getParameter');
    WebGLRenderingContext.prototype.getParameter = webglSpoof;
    if (window.WebGL2RenderingContext) {
      WebGL2RenderingContext.prototype.getParameter = webglSpoof;
    }
  } catch (e) {}

  // --- Canvas toDataURL deterministic noise ---
  // Real users' canvases vary by GPU/driver. Adding a stable per-session tweak
  // makes the fingerprint consistent across calls (matches real browser behavior)
  // but different from headless defaults.
  try {
    const sessionSeed = Math.floor(Math.random() * 10000);
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = registerNative(function toDataURL(...args) {
      const ctx = this.getContext('2d');
      if (ctx) {
        try {
          const w = this.width, h = this.height;
          if (w > 0 && h > 0) {
            const img = ctx.getImageData(0, 0, w, h);
            // Tweak 1 pixel deterministically based on session seed
            const idx = (sessionSeed % (img.data.length / 4)) * 4;
            img.data[idx] = (img.data[idx] + 1) % 256;
            ctx.putImageData(img, 0, 0);
          }
        } catch (e) {}
      }
      return origToDataURL.apply(this, args);
    }, 'toDataURL');
  } catch (e) {}

  // --- AudioContext fingerprint noise ---
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (AudioCtx) {
      const origGetChannelData = AudioBuffer.prototype.getChannelData;
      AudioBuffer.prototype.getChannelData = registerNative(function getChannelData(ch) {
        const data = origGetChannelData.call(this, ch);
        // Imperceptible deterministic tweak
        if (data.length > 0) {
          data[0] = data[0] + 1e-7;
        }
        return data;
      }, 'getChannelData');
    }
  } catch (e) {}

  // --- mediaDevices.enumerateDevices populated stub ---
  try {
    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
      const origEnum = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
      navigator.mediaDevices.enumerateDevices = registerNative(async function enumerateDevices() {
        const devices = await origEnum();
        if (devices.length > 0) return devices;
        return [
          { deviceId: 'default', kind: 'audioinput', label: '', groupId: 'group-audio-1' },
          { deviceId: 'default', kind: 'audiooutput', label: '', groupId: 'group-audio-1' },
          { deviceId: 'default', kind: 'videoinput', label: '', groupId: 'group-video-1' },
        ];
      }, 'enumerateDevices');
    }
  } catch (e) {}

  // --- speechSynthesis.getVoices populated stub ---
  try {
    if (window.speechSynthesis) {
      const origGetVoices = window.speechSynthesis.getVoices.bind(window.speechSynthesis);
      window.speechSynthesis.getVoices = registerNative(function getVoices() {
        const real = origGetVoices();
        if (real && real.length > 0) return real;
        // Fallback stubs for common en-US voices
        return [
          { name: 'Google US English', lang: 'en-US', default: true, localService: false, voiceURI: 'Google US English' },
          { name: 'Google UK English Female', lang: 'en-GB', default: false, localService: false, voiceURI: 'Google UK English Female' },
        ];
      }, 'getVoices');
    }
  } catch (e) {}

  // --- Permissions.query passthrough for notifications ---
  try {
    const origQuery = window.navigator.permissions && window.navigator.permissions.query
      ? window.navigator.permissions.query.bind(window.navigator.permissions)
      : null;
    if (origQuery) {
      window.navigator.permissions.query = registerNative(function query(params) {
        if (params && params.name === 'notifications') {
          return Promise.resolve({ state: Notification.permission, onchange: null });
        }
        return origQuery(params);
      }, 'query');
    }
  } catch (e) {}

  // --- window.chrome populated (runtime + app + csi + loadTimes) ---
  try {
    if (!window.chrome) {
      window.chrome = {};
    }
    if (!window.chrome.runtime) {
      window.chrome.runtime = {
        OnInstalledReason: { INSTALL: 'install', UPDATE: 'update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update' },
        PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformOs: { LINUX: 'linux', MAC: 'mac', WIN: 'win' },
        RequestUpdateCheckStatus: { NO_UPDATE: 'no_update' },
      };
    }
    // Real Chrome runtime exposes these as functions — detectors call them.
    if (typeof window.chrome.runtime.connect !== 'function') {
      window.chrome.runtime.connect = registerNative(function connect() {
        return {
          disconnect: registerNative(function disconnect() {}, 'disconnect'),
          postMessage: registerNative(function postMessage() {}, 'postMessage'),
          onDisconnect: { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
          onMessage: { addListener: function() {}, removeListener: function() {}, hasListener: function() { return false; } },
          name: '',
        };
      }, 'connect');
    }
    if (typeof window.chrome.runtime.sendMessage !== 'function') {
      window.chrome.runtime.sendMessage = registerNative(function sendMessage() { return undefined; }, 'sendMessage');
    }
    if (typeof window.chrome.runtime.getManifest !== 'function') {
      window.chrome.runtime.getManifest = registerNative(function getManifest() { return undefined; }, 'getManifest');
    }
    if (typeof window.chrome.runtime.getURL !== 'function') {
      window.chrome.runtime.getURL = registerNative(function getURL(path) { return 'chrome-extension://invalid/' + (path || ''); }, 'getURL');
    }
    // chrome.app / chrome.csi / chrome.loadTimes — long-deprecated but fingerprinters still check.
    if (!window.chrome.app) {
      window.chrome.app = {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
      };
    }
    if (typeof window.chrome.csi !== 'function') {
      window.chrome.csi = registerNative(function csi() {
        return { onloadT: Date.now(), startE: Date.now() - 1000, pageT: 1000, tran: 15 };
      }, 'csi');
    }
    if (typeof window.chrome.loadTimes !== 'function') {
      window.chrome.loadTimes = registerNative(function loadTimes() {
        const now = Date.now() / 1000;
        return {
          requestTime: now - 2, startLoadTime: now - 1.5, commitLoadTime: now - 1.2,
          finishDocumentLoadTime: now - 0.8, finishLoadTime: now - 0.2,
          firstPaintTime: now - 0.7, firstPaintAfterLoadTime: 0, navigationType: 'Other',
          wasFetchedViaSpdy: true, wasNpnNegotiated: true, npnNegotiatedProtocol: 'h2',
          wasAlternateProtocolAvailable: false, connectionInfo: 'h2',
        };
      }, 'loadTimes');
    }
  } catch (e) {}

  // --- iframe contentWindow re-patching ---
  // Classic bypass: create an iframe, read contentWindow.navigator.webdriver.
  // Without this, the iframe sees the unpatched native property.
  try {
    const descriptor = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
    if (descriptor && descriptor.get) {
      const origGetter = descriptor.get;
      Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get: registerNative(function contentWindow() {
          const win = origGetter.call(this);
          try {
            if (win && win.navigator) {
              Object.defineProperty(win.Navigator.prototype, 'webdriver', {
                get: () => undefined,
                configurable: true,
              });
            }
          } catch (e) {}
          return win;
        }, 'contentWindow'),
        configurable: true,
      });
    }
  } catch (e) {}
})();
"""
