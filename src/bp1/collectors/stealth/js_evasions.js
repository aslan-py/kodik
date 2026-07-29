// navigator.webdriver → undefined
Object.defineProperty(navigator, 'webdriver', {get: () => undefined, configurable: true});
delete Object.getPrototypeOf(navigator).webdriver;

// window.chrome emulation
window.chrome = {
  app: {isInstalled: false, InstallState: {DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed'}, RunningState: {CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running'}, getDetails: () => null, getIsInstalled: () => false, installState: () => 'not_installed', runningState: () => 'cannot_run'},
  runtime: {connect: () => ({onMessage: {addListener: () => {}}, postMessage: () => {}, disconnect: () => {}}), sendMessage: () => {}, id: undefined},
  csi: () => ({onloadT: Date.now(), pageT: Math.random() * 10000, startE: Date.now(), tran: 15}),
  loadTimes: () => ({commitLoadTime: performance.timing.responseStart / 1000, connectionInfo: 'h3', finishDocumentLoadTime: performance.timing.domContentLoadedEventEnd / 1000, finishLoadTime: performance.timing.loadEventEnd / 1000, firstPaintAfterLoadTime: 0, firstPaintTime: performance.timing.domContentLoadedEventEnd / 1000, navigationType: 'Other', npnNegotiatedProtocol: 'unknown', requestTime: performance.timing.navigationStart / 1000, startLoadTime: performance.timing.navigationStart / 1000, wasAlternateProtocolAvailable: false, wasFetchedViaSpdy: true, wasNpnNegotiated: false}),
};

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

// WebGL vendor/renderer spoofing
const gp = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p) {
  if (p === 37445) return 'Intel Inc.';
  if (p === 37446) return 'Intel(R) UHD Graphics 630';
  return gp.apply(this, arguments);
};
