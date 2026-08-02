// === SECTION: webdriver ===
// navigator.webdriver → undefined
Object.defineProperty(navigator, 'webdriver', {get: () => undefined, configurable: true});
delete Object.getPrototypeOf(navigator).webdriver;

// === SECTION: chrome ===
// window.chrome emulation
window.chrome = {
  app: {isInstalled: false, InstallState: {DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed'}, RunningState: {CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running'}, getDetails: () => null, getIsInstalled: () => false, installState: () => 'not_installed', runningState: () => 'cannot_run'},
  runtime: {connect: () => ({onMessage: {addListener: () => {}}, postMessage: () => {}, disconnect: () => {}}), sendMessage: () => {}, id: undefined},
  csi: () => ({onloadT: Date.now(), pageT: Math.random() * 10000, startE: Date.now(), tran: 15}),
  loadTimes: () => ({commitLoadTime: performance.timing.responseStart / 1000, connectionInfo: 'h3', finishDocumentLoadTime: performance.timing.domContentLoadedEventEnd / 1000, finishLoadTime: performance.timing.loadEventEnd / 1000, firstPaintAfterLoadTime: 0, firstPaintTime: performance.timing.domContentLoadedEventEnd / 1000, navigationType: 'Other', npnNegotiatedProtocol: 'unknown', requestTime: performance.timing.navigationStart / 1000, startLoadTime: performance.timing.navigationStart / 1000, wasAlternateProtocolAvailable: false, wasFetchedViaSpdy: true, wasNpnNegotiated: false}),
};

// === SECTION: plugins ===
// Fake plugins
const plugins = [
  {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1},
  {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1},
  {name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2},
];
const pa = Object.create(PluginArray.prototype);
for (let i = 0; i < plugins.length; i++) pa[i] = plugins[i];
Object.defineProperty(pa, 'length', {value: plugins.length});
Object.defineProperty(navigator, 'plugins', {get: () => pa, configurable: true});

// === SECTION: navigator ===
// Navigator properties
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US', 'en'], configurable: true});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32', configurable: true});
Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.', configurable: true});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8, configurable: true});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8, configurable: true});
Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0, configurable: true});

// Window dimensions
Object.defineProperty(window, 'outerWidth', {get: () => 1920, configurable: true});
Object.defineProperty(window, 'outerHeight', {get: () => 1080, configurable: true});

// === SECTION: webgl ===
// WebGL vendor/renderer spoofing (WebGL1 + WebGL2)
// Используем MutationObserver, чтобы гарантировать переопределение
// после создания WebGL-контекста
(function() {
  const VENDOR = 0x9245;
  const RENDERER = 0x9246;
  const spoofedVendor = 'Intel Inc.';
  const spoofedRenderer = 'Intel(R) UHD Graphics 630';

  const overrideWebGL = () => {
    // WebGL1
    if (typeof WebGLRenderingContext !== 'undefined') {
      const gp1 = WebGLRenderingContext.prototype.getParameter;
      WebGLRenderingContext.prototype.getParameter = function(p) {
        if (p === VENDOR) return spoofedVendor;
        if (p === RENDERER) return spoofedRenderer;
        return gp1.apply(this, arguments);
      };
    }
    // WebGL2
    if (typeof WebGL2RenderingContext !== 'undefined') {
      const gp2 = WebGL2RenderingContext.prototype.getParameter;
      WebGL2RenderingContext.prototype.getParameter = function(p) {
        if (p === VENDOR) return spoofedVendor;
        if (p === RENDERER) return spoofedRenderer;
        return gp2.apply(this, arguments);
      };
    }
  };

  // Пробуем сразу
  overrideWebGL();

  // Если WebGL2 ещё не определён — ждём через observer
  if (typeof WebGL2RenderingContext === 'undefined') {
    const observer = new MutationObserver(() => {
      if (typeof WebGL2RenderingContext !== 'undefined') {
        overrideWebGL();
        observer.disconnect();
      }
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});
    // Таймаут на случай, если observer не сработает
    setTimeout(() => {
      overrideWebGL();
      observer.disconnect();
    }, 2000);
  }
})();
