// general_lk_utils.js

const fs = require('fs');
const { By } = require('selenium-webdriver');

const SELECT_CONTRACT_BUTTON_SELECTOR = "#main > div > div > div:nth-child(3) > form > div > ul > li:nth-child(1) > div > div.contract-list__item-buttons > button";

/**
 * Reads and parses the LinkedIn credentials from a JSON file.
 * @param {string} path - Path to the credentials JSON file.
 * @returns {object|null} - The parsed credentials or null if error.
 */
function get_lk_credentials(path = "./lk_credentials.json") {
    try {
        const data = fs.readFileSync(path, 'utf8');
        return JSON.parse(data);
    } catch (err) {
        console.error("Error reading credentials file:", err);
        return null;
    }
}

/**
 * Enters the email and password into the LinkedIn sign-in form and submits it.
 * @param {object} driver - The Selenium WebDriver instance.
 * @param {string} email - The LinkedIn email.
 * @param {string} password - The LinkedIn password.
 */
async function enter_ids_on_lk_signin(driver, email, password) {
    // Wait for 2 seconds
    await driver.sleep(2000);
    const usernameInputElement = await driver.findElement(By.id("username"));
    await usernameInputElement.sendKeys(email);
    const passwordInputElement = await driver.findElement(By.id("password"));
    await passwordInputElement.sendKeys(password);
    const submitElement = await driver.findElement(By.css("#organic-div > form > div.login__form_action_container > button"));
    await driver.sleep(1000);
    await submitElement.click();
    // Wait for 5 seconds to allow for login process
    await driver.sleep(5000);
}

/**
 * Extracts a public LinkedIn profile URL from a Sales Navigator URL.
 * @param {string} url - The Sales Navigator URL.
 * @returns {string|null} - The public profile URL or null if not found.
 */
function get_lk_url_from_sales_lk_url(url) {
    // Regex to capture the LinkedIn ID between '/lead/' and the comma
    const regex = /\/lead\/(.*?),/i;
    const match = regex.exec(url);
    if (match) {
        return `https://www.linkedin.com/in/${match[1]}`;
    }
    return null;
}

/**
 * Clicks on the contract filter button in LinkedIn.
 * @param {object} driver - The Selenium WebDriver instance.
 */
async function select_contract_lk(driver) {
    const contract_filter = await driver.findElement(By.css(SELECT_CONTRACT_BUTTON_SELECTOR));
    await contract_filter.click();
    // Wait for 4 seconds after clicking
    await driver.sleep(4000);
}

/**
 * Removes a specified query parameter from a URL.
 * @param {string} url - The original URL.
 * @param {string} param - The parameter to remove.
 * @returns {string} - The updated URL.
 */
function remove_url_parameter(url, param) {
    try {
        const parsedUrl = new URL(url);
        parsedUrl.searchParams.delete(param);
        return parsedUrl.toString();
    } catch (err) {
        console.error("Error in remove_url_parameter:", err);
        return url;
    }
}

module.exports = {
    get_lk_credentials,
    enter_ids_on_lk_signin,
    get_lk_url_from_sales_lk_url,
    select_contract_lk,
    remove_url_parameter
};
