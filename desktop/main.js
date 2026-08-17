/**
 * The desktop shell. Owns the window; owns nothing about the business.
 *
 * The runtime is a separate process on purpose. Closing the window must not end
 * a run that has capital reserved and may be mid-way through an irreversible
 * action, so the window is a view onto the company rather than the company
 * itself. Quitting is an explicit choice made in the app, not a side effect of
 * clicking a close button.
 */

const { app, BrowserWindow, Menu, Tray, dialog, shell, ipcMain } = require('electron')
const { spawn } = require('node:child_process')
const http = require('node:http')
const path = require('node:path')
const fs = require('node:fs')

const PORT = Number(process.env.GUILDLESS_PORT || 8780)
const BASE = `http://127.0.0.1:${PORT}`

let mainWindow = null
let tray = null
let runtime = null
let quitting = false

/**
 * Where the runtime binary lives.
 *
 * extraResource lands it flat in resources/, so that is checked first. The
 * candidates are tried in order rather than assumed, because getting this wrong
 * produces an app that installs cleanly and then does nothing, which is the
 * hardest kind of failure to notice.
 */
function runtimePath() {
  const name = 'guildless-runtime.exe'
  const candidates = [
    path.join(process.resourcesPath || '', 'guildless-runtime', name),
    path.join(__dirname, 'dist', 'guildless-runtime', name),
    path.join(process.resourcesPath || '', name),
  ]
  return candidates.find(candidate => fs.existsSync(candidate)) || candidates[0]
}

function dataHome() {
  return path.join(app.getPath('appData'), 'Guildless')
}

/** Whether a runtime is already answering. Reused rather than replaced. */
function probe(timeoutMs = 1500) {
  return new Promise(resolve => {
    const request = http.get(`${BASE}/v1/outcome`, { timeout: timeoutMs }, response => {
      response.resume()
      resolve(response.statusCode === 200)
    })
    request.on('error', () => resolve(false))
    request.on('timeout', () => { request.destroy(); resolve(false) })
  })
}

async function waitForRuntime(attempts = 40) {
  for (let i = 0; i < attempts; i += 1) {
    if (await probe()) return true
    await new Promise(done => setTimeout(done, 700))
  }
  return false
}

async function ensureRuntime() {
  // An existing healthy runtime is left alone. Starting a second would give the
  // company two sets of books writing to one directory.
  if (await probe()) return { started: false, ok: true }

  const binary = runtimePath()
  if (!fs.existsSync(binary)) {
    return { started: false, ok: false, error: `実行エンジンが見つかりません: ${binary}` }
  }

  const home = dataHome()
  fs.mkdirSync(home, { recursive: true })
  const logPath = path.join(home, 'runtime.log')
  const log = fs.openSync(logPath, 'a')

  runtime = spawn(binary, ['--port', String(PORT)], {
    detached: true,               // survives the shell, which is the point
    stdio: ['ignore', log, log],  // and says why when it does not start
    cwd: home,
    env: { ...process.env, GUILDLESS_HOME: home },
  })
  runtime.unref()

  const ok = await waitForRuntime()
  if (ok) return { started: true, ok: true, error: '' }

  let tail = ''
  try {
    tail = fs.readFileSync(logPath, 'utf8').trim().split('
').slice(-8).join('
')
  } catch { /* nothing written */ }
  return {
    started: true, ok: false,
    error: `実行エンジンが応答しませんでした。

${tail || logPath}`,
  }
}

function stopRuntime() {
  return new Promise(resolve => {
    const request = http.request(`${BASE}/v1/runtime/stop`, { method: 'POST' }, () => resolve(true))
    request.on('error', () => {
      // No graceful endpoint yet: fall back to the process we started.
      if (runtime && !runtime.killed) {
        try { process.kill(-runtime.pid) } catch { /* already gone */ }
      }
      resolve(false)
    })
    request.end()
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#f7f7f5',
    title: 'Guildless',
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  })

  mainWindow.loadURL(BASE)

  mainWindow.on('close', event => {
    if (quitting) return
    // Closing hides. A run in progress keeps going, and the tray says so.
    event.preventDefault()
    mainWindow.hide()
  })

  // External links open in the real browser rather than replacing the app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'assets', 'tray.png'))
  tray.setToolTip('Guildless — 実行中')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '画面を開く', click: () => { mainWindow ? mainWindow.show() : createWindow() } },
    { type: 'separator' },
    { label: 'データフォルダ', click: () => shell.openPath(dataHome()) },
    { type: 'separator' },
    { label: 'Guildlessを終了', click: () => confirmQuit() },
  ]))
  tray.on('double-click', () => { mainWindow ? mainWindow.show() : createWindow() })
}

/** Quitting can abandon reserved capital, so it is confirmed rather than instant. */
async function confirmQuit() {
  let reserved = 0
  let status = 'UNKNOWN'
  try {
    const state = await new Promise((resolve, reject) => {
      http.get(`${BASE}/v1/outcome`, response => {
        let body = ''
        response.on('data', chunk => { body += chunk })
        response.on('end', () => resolve(JSON.parse(body)))
      }).on('error', reject)
    })
    reserved = state.money?.reserved_yen ?? 0
    status = state.status
  } catch { /* runtime already gone */ }

  const { response } = await dialog.showMessageBox({
    type: 'question',
    buttons: ['続行する', '安全に停止'],
    defaultId: 0,
    cancelId: 0,
    title: 'Guildlessを終了しますか',
    message: `実行状態: ${status}`,
    detail: `留保中の資金: ¥${reserved.toLocaleString('ja-JP')}\n停止すると実行が中断されます。`,
  })
  if (response === 1) {
    quitting = true
    await stopRuntime()
    app.quit()
  }
}

// One shell only. A second launch surfaces the existing window instead of
// starting another runtime beside the first.
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })

  app.whenReady().then(async () => {
    const result = await ensureRuntime()
    if (!result.ok) {
      dialog.showErrorBox('Guildlessを起動できません', result.error || '不明なエラー')
      app.quit()
      return
    }
    createWindow()
    createTray()
  })

  // Windows: closing every window does not end the company.
  app.on('window-all-closed', () => { /* stay resident */ })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
}

ipcMain.handle('guildless:stop-runtime', () => stopRuntime())
