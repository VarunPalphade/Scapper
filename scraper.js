#!/usr/bin/env node
/**
 * scraper.js
 *
 * This module implements the LinkedIn Sales Navigator scraper.
 * It exports an async function runScraper(options) which accepts an options object:
 *    {
 *      searchUrl: string,
 *      startPage: number,
 *      endPage: number,
 *      waitTimeBetweenPages: number,  // in seconds
 *      waitAfterPageLoaded: number,   // in seconds
 *      waitAfterScrollDown: number,   // in seconds
 *      saveFormat: string,            // "csv" or "xlsx"
 *      headless: boolean              // true for headless mode, false for headful mode
 *    }
 *
 * This version writes each profile’s data immediately to a CSV file as soon as it is scraped.
 * This way, if the process stops unexpectedly, you still have the data scraped up to that point.
 *
 * It uses Selenium WebDriver to interact with LinkedIn,
 * Cheerio to parse HTML, and writes data incrementally to a CSV file.
 * All log messages are written to scraper.log.
 */

const fs = require('fs');
const path = require('path');
const { Builder, By, until } = require('selenium-webdriver');
const chrome = require('selenium-webdriver/chrome');
const cheerio = require('cheerio');
const { Parser } = require('json2csv'); // Not used for incremental CSV, but kept for fallback.
const XLSX = require('xlsx');
const readline = require('readline');

// Import helper functions from general_lk_utils.js and getCompanyDetails.js
const {
  remove_url_parameter,
  get_lk_credentials,
  enter_ids_on_lk_signin,
  get_lk_url_from_sales_lk_url
} = require('./general_lk_utils');
const { getCompanyDetails } = require('./getCompanyDetails');

// ---------------- CSV Incremental Writing Helpers ----------------

/**
 * Converts an object to a CSV row given a list of headers.
 * Escapes double quotes.
 * @param {object} obj - The data object.
 * @param {string[]} headers - The header fields in desired order.
 * @returns {string} CSV-formatted row.
 */
function convertToCsvRow(obj, headers) {
  return headers.map(header => {
    let value = (obj[header] !== undefined && obj[header] !== null) ? obj[header].toString() : "";
    value = value.replace(/"/g, '""'); // escape quotes
    return `"${value}"`;
  }).join(",") + "\n";
}

/**
 * Initializes a CSV file by writing the header row.
 * @param {string} filePath - Path to CSV file.
 * @param {string[]} headers - The header fields.
 */
function initializeCsvFile(filePath, headers) {
  fs.writeFileSync(filePath, headers.map(h => `"${h}"`).join(",") + "\n", 'utf8');
}

/**
 * Appends a single row to the CSV file using an open write stream.
 * @param {object} rowData - The data object.
 * @param {string[]} headers - The header fields.
 * @param {WriteStream} stream - The write stream.
 */
function appendCsvRow(rowData, headers, stream) {
  stream.write(convertToCsvRow(rowData, headers));
}

// Define CSV headers (adjust as needed to match your profile object keys)
const csvHeaders = [
  "name", "first_name", "last_name", "link_to_profile",
  "connection_level", "has_linkedin_premium", "role_name",
  "company_name", "link_to_company", "time_in_company",
  "additional_info", "time_scraped", "linkedin_url",
  "website", "industry", "companySize", "headquarters", "specialties"
];

// ---------------- Logging Helpers ----------------
const logFilePath = path.join(__dirname, "scraper.log");
function logInfo(message) {
  const msg = `${new Date().toISOString()} INFO: ${message}`;
  console.log(msg);
  fs.appendFileSync(logFilePath, msg + "\n", { encoding: 'utf8' });
}
function logError(message, error) {
  const errMsg = error ? (error.stack || error) : '';
  const msg = `${new Date().toISOString()} ERROR: ${message} ${errMsg}`;
  console.error(msg);
  fs.appendFileSync(logFilePath, msg + "\n", { encoding: 'utf8' });
}

// ---------------- Sleep Helper ----------------
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ---------------- Utility: getFullLink ----------------
function getFullLink(url) {
  try {
    if (!url.startsWith('http')) {
      return 'https://www.linkedin.com' + url;
    }
    return url;
  } catch (err) {
    logError("Error in getFullLink", err);
    return url;
  }
}

// ---------------- Extraction Functions using Cheerio ----------------
function getNameInfoFromResultEl($, element) {
  try {
    const selector = "div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > div > div.artdeco-entity-lockup__content.ember-view > div.flex.flex-wrap.align-items-center > div.artdeco-entity-lockup__title.ember-view > a";
    const el = $(element).find(selector).first();
    let name = "";
    let link_to_profile = "";
    if (el.length > 0) {
      const relative_link = el.attr('href');
      link_to_profile = getFullLink(relative_link);
      name = el.text().trim();
    }
    return { name, link_to_profile };
  } catch (err) {
    logError("Error in getNameInfoFromResultEl", err);
    return { name: "", link_to_profile: "" };
  }
}

function getConnectionLevelInfoFromResultEl($, element) {
  try {
    const selector = "div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > div > div.artdeco-entity-lockup__content.ember-view > div.flex.flex-wrap.align-items-center > div.artdeco-entity-lockup__badge.ember-view.ml1 > span.artdeco-entity-lockup__degree";
    const el = $(element).find(selector).first();
    let connection_level = "";
    if (el.length > 0) {
      connection_level = el.contents().first().text().trim().replace("·\xa0", "");
    }
    return { connection_level };
  } catch (err) {
    logError("Error in getConnectionLevelInfoFromResultEl", err);
    return { connection_level: "" };
  }
}

function getLinkedinPremiumInfoFromResultEl($, element) {
  try {
    const selector = "div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > div > div.artdeco-entity-lockup__content.ember-view > div.inline-flex > div > li-icon";
    const el = $(element).find(selector);
    const has_linkedin_premium = el.length > 0;
    return { has_linkedin_premium };
  } catch (err) {
    logError("Error in getLinkedinPremiumInfoFromResultEl", err);
    return { has_linkedin_premium: false };
  }
}

function getRoleInfoFromResultEl($, element) {
  try {
    const selector = "div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > div > div.artdeco-entity-lockup__content.ember-view > div.artdeco-entity-lockup__subtitle.ember-view.t-14 > span";
    const el = $(element).find(selector).first();
    let role_name = "";
    if (el.length > 0) {
      role_name = el.contents().first().text().trim();
    }
    return { role_name };
  } catch (err) {
    logError("Error in getRoleInfoFromResultEl", err);
    return { role_name: "" };
  }
}

function getCompanyInfoFromResultEl($, element) {
  try {
    const selector = "div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > div > div.artdeco-entity-lockup__content.ember-view > div.artdeco-entity-lockup__subtitle.ember-view.t-14 > a";
    const el = $(element).find(selector).first();
    let company_name = "";
    let link_to_company = "";
    if (el.length > 0) {
      const relative_link = el.attr('href');
      link_to_company = getFullLink(relative_link);
      company_name = el.text().trim();
    }
    return { company_name, link_to_company };
  } catch (err) {
    logError("Error in getCompanyInfoFromResultEl", err);
    return { company_name: "", link_to_company: "" };
  }
}

function getTimeInCompanyInfoFromResultEl($, element) {
  try {
    const selector = "div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > div > div.artdeco-entity-lockup__content.ember-view > div.artdeco-entity-lockup__metadata.ember-view";
    const el = $(element).find(selector).first();
    let time_in_company = "";
    if (el.length > 0) {
      let texts = [];
      el.contents().each((i, elChild) => {
        if (elChild.type === 'text') {
          const txt = $(elChild).text().trim().replace("\xa0", " ");
          if (txt) texts.push(txt);
        }
      });
      time_in_company = texts.join(" | ");
    }
    return { time_in_company };
  } catch (err) {
    logError("Error in getTimeInCompanyInfoFromResultEl", err);
    return { time_in_company: "" };
  }
}

function getAdditionalInfoFromResultEl($, element) {
  try {
    const selector = "div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.ml8.pl1 > dl > div > dd > div > span";
    const elements = $(element).find(selector);
    let additional_info = "";
    if (elements.length > 1) {
      let texts = [];
      elements.eq(1).contents().each((i, elChild) => {
        const htmlString = $(elChild).toString();
        if (!htmlString.includes("<span") && !htmlString.includes("<button")) {
          const txt = $(elChild).text().trim().replace("\xa0", " ");
          if (txt) texts.push(txt);
        }
      });
      additional_info = texts.join(" | ");
    }
    return { additional_info };
  } catch (err) {
    logError("Error in getAdditionalInfoFromResultEl", err);
    return { additional_info: "" };
  }
}

function getInfoFromResultEl($, element) {
  try {
    let info = {};
    Object.assign(info,
      getNameInfoFromResultEl($, element),
      getConnectionLevelInfoFromResultEl($, element),
      getLinkedinPremiumInfoFromResultEl($, element),
      getRoleInfoFromResultEl($, element),
      getCompanyInfoFromResultEl($, element),
      getTimeInCompanyInfoFromResultEl($, element),
      getAdditionalInfoFromResultEl($, element)
    );
    info.time_scraped = Date.now();
    return info;
  } catch (err) {
    logError("Error in getInfoFromResultEl", err);
    return {};
  }
}

// ---------------- Page Parsing Helpers ----------------
function getResultEls(pageSource) {
  try {
    const $ = cheerio.load(pageSource);
    return $('#search-results-container > div > ol > li');
  } catch (err) {
    logError("Error in getResultEls", err);
    return [];
  }
}

async function getAllInfoFromPageSource(pageSource) {
  try {
    logInfo("Getting all result elements...");
    const $ = cheerio.load(pageSource);
    const resultEls = $('#search-results-container > div > ol > li');
    logInfo(`Found ${resultEls.length} elements.`);
    let infos = [];
    resultEls.each((i, elem) => {
      try {
        const info = getInfoFromResultEl($, elem);
        infos.push(info);
      } catch (err) {
        logError(`Error processing element ${i}`, err);
      }
    });
    return infos;
  } catch (err) {
    logError("Error in getAllInfoFromPageSource", err);
    return [];
  }
}

// ---------------- Scrolling & Scraping Logic ----------------
async function getAllInfoFromSearchUrl(driver, url, wait_after_page_loaded = 8000, wait_after_scroll_down = 1000, max_scroll_attempts = 5) {
  try {
    await driver.get(url);
    logInfo(`Navigated to URL: ${url}`);
  } catch (err) {
    logError(`Error navigating to URL ${url}`, err);
    return [];
  }
  try {
    logInfo("Waiting for the search results container to become visible...");
    await driver.wait(until.elementLocated(By.id("search-results-container")), wait_after_page_loaded);
    logInfo("Search results container is visible.");
  } catch (err) {
    logError("Error waiting for search results container.", err);
    return [];
  }
  
  // Gradually scroll through the container.
  try {
    const scrollHeight = await driver.executeScript("return document.getElementById('search-results-container').scrollHeight;");
    const steps = 10;
    const delay_per_step = 500;
    for (let i = 0; i < steps; i++) {
      const newScroll = ((i + 1) / steps) * scrollHeight;
      await driver.executeScript("document.getElementById('search-results-container').scrollTop = arguments[0];", newScroll);
      logInfo(`Scrolled to ${newScroll} of ${scrollHeight}`);
      await sleep(delay_per_step);
    }
  } catch (err) {
    logError("Error during gradual scrolling.", err);
  }
  
  let lastCount = -1;
  let scroll_attempt = 0;
  while (scroll_attempt < max_scroll_attempts) {
    try {
      const exists = await driver.executeScript("return document.getElementById('search-results-container') != null;");
      if (exists) {
        await driver.executeScript("document.getElementById('search-results-container').scrollTop = document.getElementById('search-results-container').scrollHeight;");
      } else {
        logInfo("Scroll container not found; breaking scroll loop.");
        break;
      }
    } catch (err) {
      logError("Error executing scroll command.", err);
      break;
    }
    await sleep(wait_after_scroll_down);
    const pageSource = await driver.getPageSource();
    const count = getResultEls(pageSource).length;
    logInfo(`Scrolling attempt ${scroll_attempt + 1}. Found ${count} profiles.`);
    if (count === lastCount) {
      logInfo("No new profiles loaded; stopping scroll.");
      break;
    }
    lastCount = count;
    scroll_attempt++;
  }
  
  const finalPageSource = await driver.getPageSource();
  return await getAllInfoFromPageSource(finalPageSource);
}

async function scrapLksnPages(driver, pageList, getSearchUrl, wait_time_between_pages = 2000, wait_after_page_loaded = 2000, wait_after_scroll_down = 2000, csvStream) {
  let totalInfo = [];
  const totalPages = pageList.length;
  for (let i = 0; i < totalPages; i++) {
    const p = pageList[i];
    logInfo(`Waiting for ${wait_time_between_pages / 1000}s before processing page ${p}...`);
    await sleep(wait_time_between_pages);
    logInfo(`Processing page ${p}...`);
    const info = await getAllInfoFromSearchUrl(driver, getSearchUrl(p), wait_after_page_loaded, wait_after_scroll_down);
    
    // For each profile scraped on this page, process it and update progress incrementally.
    const profilesCount = info.length || 1; // Avoid division by zero.
    for (let j = 0; j < info.length; j++) {
      const profile = info[j];
      
      // Process name splitting.
      if (profile.name) {
        let tokens = profile.name.trim().split(" ");
        profile.first_name = tokens[0] || "";
        profile.last_name = tokens.length > 1 ? tokens.slice(1).join(" ") : "";
      } else {
        profile.first_name = "";
        profile.last_name = "";
      }
      // Append linkedin_url.
      profile.linkedin_url = get_lk_url_from_sales_lk_url(profile.link_to_profile || "");
      
      // If company URL exists, extract company details.
      if (profile.link_to_company) {
        logInfo(`Extracting company details for: ${profile.link_to_company}`);
        await sleep(2000);
        const companyInfo = await getCompanyDetails(profile.link_to_company, driver);
        Object.assign(profile, companyInfo);
      }
      
      // Write the profile row to CSV immediately.
      appendCsvRow(profile, csvHeaders, csvStream);
      totalInfo.push(profile);
      
      // Calculate incremental progress.
      const progress = Math.round(((i + ((j + 1) / profilesCount)) / totalPages) * 100);
      global.mainWindow.webContents.send('scrape-progress', { progress: progress });
      global.mainWindow.webContents.send('scrape-log', { message: `Processed profile ${j + 1} of page ${p} (${progress}%)` });
    }
    
    // Log at the end of the page.
    global.mainWindow.webContents.send('scrape-log', { message: `Finished processing page ${p}.` });
  }
  return totalInfo;
}

// ---------------- Main Exported Function ----------------
async function runScraper(options) {
  const {
    searchUrl,
    startPage,
    endPage,
    waitTimeBetweenPages,
    waitAfterPageLoaded,
    waitAfterScrollDown,
    saveFormat,
    headless
  } = options;

  // Convert seconds to milliseconds.
  const wait_time_between_pages = waitTimeBetweenPages * 1000;
  const wait_after_page_loaded = waitAfterPageLoaded * 1000;
  const wait_after_scroll_down = waitAfterScrollDown * 1000;
  const search_url_base = remove_url_parameter(searchUrl, "page");

  // Initialize CSV file and stream.
  const outputDir = path.join(__dirname, "lksn_data");
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir);
  }
  const fileName = `${Date.now()}_lk_salesnav_export.csv`;
  const outputPath = path.join(outputDir, fileName);
  initializeCsvFile(outputPath, csvHeaders);
  const csvStream = fs.createWriteStream(outputPath, { flags: 'a' });
  logInfo(`CSV file initialized at ${outputPath}`);

  // Configure Chrome options.
  const chromeOptions = new chrome.Options();
  if (headless === true) {
    chromeOptions.addArguments("--headless", "--disable-gpu");
    logInfo("Running in headless mode.");
  } else {
    logInfo("Running in headful mode.");
  }
  chromeOptions.addArguments("--force-device-scale-factor=1", "--high-dpi-support=1", "window-size=1366,768");
  const driver = await new Builder().forBrowser('chrome').setChromeOptions(chromeOptions).build();

  let resultData = [];
  try {
    await driver.manage().window().maximize();
    await driver.get("https://www.linkedin.com/login/");
    
    const LK_CREDENTIALS_PATH = "./lk_credentials.json";
    const lk_credentials = get_lk_credentials(LK_CREDENTIALS_PATH);
    await enter_ids_on_lk_signin(driver, lk_credentials.email, lk_credentials.password);
    
    const currentUrl = await driver.getCurrentUrl();
    if (currentUrl.includes("checkpoint/challenge")) {
      logInfo("Double factor authentication required. Please complete 2FA in the browser, then press Enter in the console.");
      await new Promise(resolve => {
        process.stdin.once('data', () => resolve());
      });
    }
    
    await driver.get(searchUrl);
    await driver.executeScript("document.body.style.zoom='80%'");
    logInfo("Starting the scraping process...");

    // Create an array of pages to scrape.
    let pageList = [];
    for (let p = startPage; p <= endPage; p++) {
      pageList.push(p);
    }
    resultData = await scrapLksnPages(driver, pageList, (p) => `${search_url_base}&page=${p}`, wait_time_between_pages, wait_after_page_loaded, wait_after_scroll_down, csvStream);
    
    logInfo(`Scraping completed. Total profiles scraped: ${resultData.length}`);
  } catch (err) {
    logError("An error occurred in the scraping process.", err);
    throw err;
  } finally {
    try {
      await driver.quit();
    } catch (err) {
      logError("Error closing the driver", err);
    }
    csvStream.end();
  }

  return {
    scrapedData: resultData,
    downloadInfo: {
      fileName: fileName,
      outputPath: outputPath
    }
  };
}

module.exports = { runScraper };
