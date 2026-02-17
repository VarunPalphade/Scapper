const { ipcRenderer } = require('electron');

// Listen for progress updates from the main process
ipcRenderer.on('scrape-progress', (event, data) => {
  const progressBar = document.getElementById('progress-bar');
  const progressText = document.getElementById('progress-text');
  progressBar.value = data.progress;
  progressText.innerText = data.progress + '%';
});

// Listen for log messages from the main process
ipcRenderer.on('scrape-log', (event, data) => {
  const logView = document.getElementById('log-view');
  logView.innerHTML += data.message + '<br>';
  logView.scrollTop = logView.scrollHeight;
});

document.getElementById('scrapeForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  // Get scraping options from the form
  const startPage = parseInt(document.getElementById('startPage').value) || 1;
  const endPage = parseInt(document.getElementById('endPage').value) || 1;
  const waitTimeBetweenPages = parseInt(document.getElementById('waitTimeBetweenPages').value) || 5;
  const waitAfterPageLoaded = parseInt(document.getElementById('waitAfterPageLoaded').value) || 3;
  const waitAfterScrollDown = parseInt(document.getElementById('waitAfterScrollDown').value) || 3;
  const saveFormat = document.getElementById('saveFormat').value;
  const headless = document.getElementById('headless').checked;
  
  // Get current URL from the webview
  const webview = document.getElementById('salesNavigatorWebview');
  const searchUrl = webview.getURL();
  
  // Build the options object
  const args = {
    searchUrl,
    startPage,
    endPage,
    waitTimeBetweenPages,
    waitAfterPageLoaded,
    waitAfterScrollDown,
    saveFormat,
    headless
  };
  
  // Inform the user that scraping is in progress
  document.getElementById('result').innerText = "Scraping in progress...";
  
  // Send the scraping request to the main process
  const result = await ipcRenderer.invoke('start-scraping', args);
  if (result.success) {
    const downloadInfo = result.data.downloadInfo;
    document.getElementById('result').innerText = `Data saved to ${downloadInfo.outputPath}`;
  } else {
    document.getElementById('result').innerText = `Scraping failed: ${result.error}`;
  }
});
