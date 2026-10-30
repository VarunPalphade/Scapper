"""
This is meant to be run as a CLI script.
It will scrap the search results of a LinkedIn Sales Navigator search.

Example usage:
python lksn_search_scraper.py --search-url "https://www.linkedin.com/sales/search/people?query=(spellCorrectionEnabled%3Atrue%2Ckeywords%3Ascraping)"
"""

import argparse
import os
import logging
from bs4 import BeautifulSoup
from tqdm import tqdm
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pandas as pd
from general_lk_utils import (
    remove_url_parameter,
    get_lk_credentials,
    enter_ids_on_lk_signin,
    get_lk_url_from_sales_lk_url,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure logging to file (and console, if desired)
logging.basicConfig(
    filename="scraper.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

SCROLL_TO_BOTTOM_COMMAND = (
    "document.getElementById('search-results-container').scrollTop+=100000;"
)
LK_CREDENTIALS_PATH = "./lk_credentials.json"


def get_full_link(url):
    try:
        if not url.startswith("http"):
            return "https://www.linkedin.com" + url
        return url
    except Exception as e:
        logging.error("Error in get_full_link: %s", e, exc_info=True)
        return url


def get_name_info_from_result_el(result_el):
    try:
        selector = ("div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > "
                    "div > div.artdeco-entity-lockup__content.ember-view > div.flex.flex-wrap.align-items-center > "
                    "div.artdeco-entity-lockup__title.ember-view > a")
        els = result_el.select(selector)
        link_to_profile = ""
        name = ""
        if len(els) > 0:
            relative_link = els[0]["href"]
            link_to_profile = get_full_link(relative_link)
            name = els[0].get_text().strip()
        return {"name": name, "link_to_profile": link_to_profile}
    except Exception as e:
        logging.error("Error in get_name_info_from_result_el: %s", e, exc_info=True)
        return {"name": "", "link_to_profile": ""}


def get_connection_level_info_from_result_el(result_el):
    try:
        selector = ("div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > "
                    "div > div.artdeco-entity-lockup__content.ember-view > div.flex.flex-wrap.align-items-center > "
                    "div.artdeco-entity-lockup__badge.ember-view.ml1 > span.artdeco-entity-lockup__degree")
        els = result_el.select(selector)
        connection_level = ""
        if len(els) > 0:
            el_contents = els[0].contents
            if len(el_contents) > 0:
                connection_level = el_contents[0].strip().replace("·\xa0", "")
        return {"connection_level": connection_level}
    except Exception as e:
        logging.error("Error in get_connection_level_info_from_result_el: %s", e, exc_info=True)
        return {"connection_level": ""}


def build_search_url(search_url_base, page=1):
    try:
        # Always append the page parameter to force a reload
        return search_url_base + f"&page={page}"
    except Exception as e:
        logging.error("Error in build_search_url: %s", e, exc_info=True)
        return search_url_base



def get_linkedin_premium_info_from_result_el(result_el):
    try:
        selector = ("div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > "
                    "div > div.artdeco-entity-lockup__content.ember-view > div.inline-flex > div > li-icon")
        els = result_el.select(selector)
        has_linkedin_premium = False
        if len(els) > 0:
            has_linkedin_premium = True
        return {"has_linkedin_premium": has_linkedin_premium}
    except Exception as e:
        logging.error("Error in get_linkedin_premium_info_from_result_el: %s", e, exc_info=True)
        return {"has_linkedin_premium": False}


def get_role_info_from_result_el(result_el):
    try:
        selector = ("div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > "
                    "div > div.artdeco-entity-lockup__content.ember-view > div.artdeco-entity-lockup__subtitle.ember-view.t-14 > span")
        els = result_el.select(selector)
        role_name = ""
        if len(els) > 0:
            el_contents = els[0].contents
            if len(el_contents) > 0:
                role_name = el_contents[0].strip()
        return {"role_name": role_name}
    except Exception as e:
        logging.error("Error in get_role_info_from_result_el: %s", e, exc_info=True)
        return {"role_name": ""}


def get_company_info_from_result_el(result_el):
    try:
        selector = ("div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > "
                    "div > div.artdeco-entity-lockup__content.ember-view > "
                    "div.artdeco-entity-lockup__subtitle.ember-view.t-14 > a")
        els = result_el.select(selector)
        link_to_company = ""
        company_name = ""
        if len(els) > 0:
            relative_link = els[0]["href"]
            link_to_company = get_full_link(relative_link)
            company_name = els[0].get_text().strip()
        return {"link_to_company": link_to_company, "company_name": company_name}
    except Exception as e:
        logging.error("Error in get_company_info_from_result_el: %s", e, exc_info=True)
        return {"link_to_company": "", "company_name": ""}


def get_time_in_company_info_from_result_el(result_el):
    try:
        selector = ("div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > div.mb3 > "
                    "div > div.artdeco-entity-lockup__content.ember-view > div.artdeco-entity-lockup__metadata.ember-view")
        els = result_el.select(selector)
        time_in_company = ""
        if len(els) > 0:
            el_contents = els[0].contents
            if len(el_contents) > 0:
                time_in_company = " | ".join(
                    [el_contents[i].strip().replace("\xa0", " ") for i in range(len(el_contents))
                     if "<span" not in str(el_contents[i])]
                )
        return {"time_in_company": time_in_company}
    except Exception as e:
        logging.error("Error in get_time_in_company_info_from_result_el: %s", e, exc_info=True)
        return {"time_in_company": ""}


def get_additional_info_from_result_el(result_el):
    try:
        selector = ("div > div > div.flex.justify-space-between.full-width > div.flex.flex-column > "
                    "div.ml8.pl1 > dl > div > dd > div > span")
        els = result_el.select(selector)
        additional_info = ""
        if len(els) > 1:
            el_contents = els[1].contents
            if len(el_contents) > 0:
                additional_info = " | ".join(
                    [el_contents[i].strip().replace("\xa0", " ") for i in range(len(el_contents))
                     if "<span" not in str(el_contents[i]) and "<button" not in str(el_contents[i])]
                )
        return {"additional_info": additional_info}
    except Exception as e:
        logging.error("Error in get_additional_info_from_result_el: %s", e, exc_info=True)
        return {"additional_info": ""}


def get_info_from_result_el(result_el):
    try:
        info = {}
        info.update(get_name_info_from_result_el(result_el))
        info.update(get_connection_level_info_from_result_el(result_el))
        info.update(get_linkedin_premium_info_from_result_el(result_el))
        info.update(get_role_info_from_result_el(result_el))
        info.update(get_company_info_from_result_el(result_el))
        info.update(get_time_in_company_info_from_result_el(result_el))
        info.update(get_additional_info_from_result_el(result_el))
        info["time_scraped"] = int(time.time() * 1000)
        return info
    except Exception as e:
        logging.error("Error in get_info_from_result_el: %s", e, exc_info=True)
        return {}


def get_result_els(page_source):
    try:
        soup = BeautifulSoup(page_source, "html.parser")
        full_results_selector = "#search-results-container > div > ol > li"
        all_results_el = soup.select(full_results_selector)
        return all_results_el
    except Exception as e:
        logging.error("Error in get_result_els: %s", e, exc_info=True)
        return []


def get_all_info_from_page_source(page_source):
    try:
        logging.info("Getting all result elements...")
        result_els = get_result_els(page_source)
        n = len(result_els)
        logging.info(f"Found {n} elements.")
        logging.info("Getting the info for all elements...")
        infos = []
        for i in tqdm(range(n)):
            try:
                new_info = get_info_from_result_el(result_els[i])
                infos.append(new_info)
            except Exception as e:
                logging.error(f"Error processing element {i}: {e}", exc_info=True)
        return infos
    except Exception as e:
        logging.error("Error in get_all_info_from_page_source: %s", e, exc_info=True)
        return []


def get_all_info_from_search_url(driver, url, wait_after_page_loaded=8, wait_after_scroll_down=1, max_scroll_attempts=5):
    try:
        driver.get(url)
        logging.info(f"Navigated to URL: {url}")
    except Exception as e:
        logging.error(f"Error navigating to URL {url}: {e}", exc_info=True)
        return []
    try:
        logging.info("Waiting for the search results container to become visible...")
        wait = WebDriverWait(driver, wait_after_page_loaded)
        container = wait.until(EC.visibility_of_element_located((By.ID, "search-results-container")))
        logging.info("Search results container is visible.")
    except Exception as e:
        logging.error("Error waiting for search results container.", exc_info=True)
        return []
    
    # Gradually scroll through the container
    try:
        if container:
            logging.info("Gradually scrolling down the container to load all profiles...")
            scroll_height = driver.execute_script("return document.getElementById('search-results-container').scrollHeight;")
            steps = 10
            delay_per_step = 0.5
            for i in range(steps):
                new_scroll = (i + 1) / steps * scroll_height
                driver.execute_script("document.getElementById('search-results-container').scrollTop = arguments[0];", new_scroll)
                logging.info(f"Scrolled to {new_scroll} of {scroll_height}")
                time.sleep(delay_per_step)
        else:
            logging.warning("Scroll container not found; skipping gradual scroll.")
    except Exception as e:
        logging.error("Error during gradual scrolling.", exc_info=True)
    
    # Additional scroll attempts until no new profiles are loaded
    last_count = -1
    scroll_attempt = 0
    while scroll_attempt < max_scroll_attempts:
        try:
            exists = driver.execute_script("return document.getElementById('search-results-container') != null;")
            if exists:
                driver.execute_script("document.getElementById('search-results-container').scrollTop = document.getElementById('search-results-container').scrollHeight;")
            else:
                logging.warning("Scroll container not found; breaking scroll loop.")
                break
        except Exception as e:
            logging.error("Error executing scroll command.", exc_info=True)
            break

        def profiles_loaded(driver):
            return len(get_result_els(driver.page_source)) > last_count

        try:
            WebDriverWait(driver, wait_after_scroll_down).until(profiles_loaded)
        except Exception as e:
            logging.warning("Timeout waiting for new profiles to load.", exc_info=True)

        current_count = len(get_result_els(driver.page_source))
        logging.info(f"Scrolling attempt {scroll_attempt + 1}. Found {current_count} profiles.")
        if current_count == last_count:
            logging.info("No new profiles loaded; stopping scroll.")
            break
        last_count = current_count
        scroll_attempt += 1

    page_source = driver.page_source
    return get_all_info_from_page_source(page_source)


def scrap_lksn_pages(driver, page_list, get_search_url, wait_time_between_pages=2, wait_after_page_loaded=2, wait_after_scroll_down=2):
    total_info = []
    for p in page_list:
        try:
            logging.info(f"Waiting for {wait_time_between_pages}s before processing page {p}...")
            time.sleep(wait_time_between_pages)
            logging.info(f"Processing page {p}...")
            info = get_all_info_from_search_url(
                driver,
                get_search_url(p),
                wait_after_page_loaded=wait_after_page_loaded,
                wait_after_scroll_down=wait_after_scroll_down,
            )
            total_info.extend(info)
        except Exception as e:
            logging.error(f"Error processing page {p}: {e}", exc_info=True)
    return total_info


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Scrap LinkedIn Sales Navigator")
        parser.add_argument("--search-url", type=str, help="The url of the search page to scrap", required=True)
        parser.add_argument("--start-page", type=int, help="The page to start scrapping from", required=False, default=1)
        parser.add_argument("--end-page", type=int, help="The page to end scrapping at", required=False, default=1)
        parser.add_argument("--wait-time-between-pages", type=int, help="The time in seconds to wait between pages", required=False, default=5)
        parser.add_argument("--wait-after-page-loaded", type=int, help="The time in seconds to wait after the page is loaded", required=False, default=3)
        parser.add_argument("--wait-after-scroll-down", type=int, help="The time in seconds to wait after scrolling down", required=False, default=3)
        parser.add_argument("--save-format", type=str, help="The format to save the data in (xlsx or csv)", required=False, default="csv")
        args = parser.parse_args()

        search_url = args.search_url
        start_page = args.start_page
        end_page = args.end_page
        wait_time_between_pages = args.wait_time_between_pages
        wait_after_page_loaded = args.wait_after_page_loaded
        wait_after_scroll_down = args.wait_after_scroll_down
        save_format = args.save_format
        search_url_base = remove_url_parameter(search_url, "page")

        logging.info("Starting the driver...")
        logging.getLogger("selenium").setLevel(logging.CRITICAL)
        
        # Configure ChromeOptions with a smaller window size
        chrome_options = Options()
        chrome_options.add_argument("--force-device-scale-factor=1")
        chrome_options.add_argument("--high-dpi-support=1")
        chrome_options.add_argument("window-size=1366,768")
        driver = webdriver.Chrome(options=chrome_options)
        driver.maximize_window()
        driver.get("https://www.linkedin.com/login/")

        logging.info("Inputting the credentials...")
        lk_credentials = get_lk_credentials(LK_CREDENTIALS_PATH)
        enter_ids_on_lk_signin(driver, lk_credentials["email"], lk_credentials["password"])

        if "checkpoint/challenge" in driver.current_url:
            logging.warning("Double factor authentication required. Awaiting user action...")
            input("Complete 2FA and press Enter to continue...")

        driver.get(search_url)
        driver.execute_script("document.body.style.zoom='80%'")
        logging.info("Starting the scraping process...")

        lksnSearchInfos = scrap_lksn_pages(
            driver,
            page_list=range(start_page, end_page + 1),
            get_search_url=lambda x: build_search_url(search_url_base, x),
            wait_time_between_pages=wait_time_between_pages,
            wait_after_page_loaded=wait_after_page_loaded,
            wait_after_scroll_down=wait_after_scroll_down,
        )


        df = pd.DataFrame(lksnSearchInfos)
        df["linkedin_url"] = df.link_to_profile.apply(get_lk_url_from_sales_lk_url)

        if save_format == "csv":
            if not os.path.exists("lksn_data"):
                os.makedirs("lksn_data")
            file_name = f"{str(int(time.time()*1000))}_lk_salesnav_export.csv"
            df.to_csv(f"./lksn_data/{file_name}", index=False)
            logging.info(f"Data saved to ./lksn_data/{file_name}")
        else:
            if not os.path.exists("lksn_data"):
                os.makedirs("lksn_data")
            file_name = f"{str(int(time.time()*1000))}_lk_salesnav_export.xlsx"
            df.to_excel(f"./lksn_data/{file_name}", index=False)
            logging.info(f"Data saved to ./lksn_data/{file_name}")
    except Exception as main_e:
        logging.error("An error occurred in the main execution block.", exc_info=True)
    finally:
        try:
            driver.close()
        except Exception as e:
            logging.error("Error closing the driver: %s", e, exc_info=True)
