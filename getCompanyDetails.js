const { By, until } = require('selenium-webdriver');
const cheerio = require('cheerio');

/**
 * Cleans the company URL by removing "/sales" and any query parameters,
 * so that we navigate to the official LinkedIn company page.
 * @param {string} companyUrl - The original company URL.
 * @returns {string} - The cleaned URL.
 */
function cleanCompanyUrl(companyUrl) {
  try {
    const urlObj = new URL(companyUrl);
    // Remove "/sales" from the pathname.
    urlObj.pathname = urlObj.pathname.replace('/sales', '');
    // Clear any query parameters.
    urlObj.search = "";
    return urlObj.toString();
  } catch (err) {
    console.error("Error cleaning company URL:", err);
    return companyUrl;
  }
}

/**
 * Sleeps for the specified number of milliseconds.
 * @param {number} ms - Milliseconds to sleep.
 * @returns {Promise}
 */
async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Extracts company details from a LinkedIn company's About page.
 *
 * It navigates to the official company About page (after cleaning the URL),
 * scrolls the page until no new content is loaded (to trigger any lazy-loading),
 * and then uses Cheerio to extract fields such as:
 *   - Website
 *   - Industry
 *   - Company size
 *   - Headquarters
 *   - Specialties
 *
 * @param {string} companyUrl - The LinkedIn URL of the company (e.g., "https://www.linkedin.com/company/equans").
 * @param {object} driver - The active Selenium WebDriver instance.
 * @param {number} [timeout=10000] - Maximum wait time for page elements in milliseconds.
 * @returns {object} - An object with keys: website, industry, companySize, headquarters, specialties.
 */
async function getCompanyDetails(companyUrl, driver, timeout = 10000) {
  let companyDetails = {
    website: "",
    industry: "",
    companySize: "",
    headquarters: "",
    specialties: "",
  };

  try {
    // Clean the URL and construct the About page URL.
    companyUrl = cleanCompanyUrl(companyUrl);
    const aboutUrl = companyUrl.endsWith('/') ? companyUrl + 'about' : companyUrl + '/about';
    console.log(`Navigating to company About page: ${aboutUrl}`);
    await driver.get(aboutUrl);

    // Wait for the definition list to appear. We assume the details are inside a <dl> element.
    await driver.wait(until.elementLocated(By.css('dl')), timeout);

    // Scroll the whole page repeatedly until the scroll height stops changing.
    let lastHeight = await driver.executeScript("return document.body.scrollHeight;");
    while (true) {
      await driver.executeScript("window.scrollTo(0, document.body.scrollHeight);");
      await sleep(1000);
      let newHeight = await driver.executeScript("return document.body.scrollHeight;");
      if (newHeight === lastHeight) {
        break;
      }
      lastHeight = newHeight;
    }
    await sleep(2000); // Wait extra time for any content to load.

    // Get the updated page source.
    const pageSource = await driver.getPageSource();
    const $ = cheerio.load(pageSource);

    // Iterate over each <dt> element with class "mb1" (the field labels).
    $('dt.mb1').each((i, elem) => {
      // Read the label text from the h3 element.
      const label = $(elem).find('h3.text-heading-medium').text().trim();
      // The corresponding <dd> is expected to be the immediate sibling.
      const ddElem = $(elem).next('dd');
      let value = ddElem.text().trim();

      // For the Website field, try to fetch the text from the anchor if available.
      if (label === "Website") {
        const anchorText = ddElem.find('a').text().trim();
        if (anchorText) {
          value = anchorText;
        }
      }
      
      // Map the label to the corresponding key.
      switch (label) {
        case "Website":
          companyDetails.website = value;
          break;
        case "Industry":
          companyDetails.industry = value;
          break;
        case "Company size":
          // Sometimes additional text (like associated members) is present; take only the first line.
          companyDetails.companySize = value.split('\n')[0].trim();
          break;
        case "Headquarters":
          companyDetails.headquarters = value;
          break;
        case "Specialties":
          companyDetails.specialties = value;
          break;
        default:
          break;
      }
    });

    console.log("Extracted company details:", companyDetails);
  } catch (err) {
    console.error(`Error extracting company details from ${companyUrl}:`, err);
  }

  return companyDetails;
}

module.exports = { getCompanyDetails };
