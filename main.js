const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { runScraper } = require('./scraper');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webviewTag: true  // Enable the webview tag for embedded browsing.
    }
  });
  mainWindow.loadFile('index.html');
  // Store the reference globally so that the scraper can use it for sending progress updates.
  global.mainWindow = mainWindow;
}

app.whenReady().then(createWindow);

ipcMain.handle('start-scraping', async (event, args) => {
  try {
    // runScraper can now reference global.mainWindow to send IPC messages for progress and logs.
    const result = await runScraper(args);
    return { success: true, data: result };
  } catch (error) {
    console.error("Scraping error:", error);
    return { success: false, error: error.message };
  }
});
