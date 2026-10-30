import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import re
from general_lk_utils import (
    remove_url_parameter,
    get_lk_credentials,
    enter_ids_on_lk_signin,
    get_lk_url_from_sales_lk_url,
)

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
        for i in range(n):
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

def build_search_url(search_url_base, page=1):
    # If the URL already contains a "page" parameter, replace it.
    if "page=" in search_url_base:
        url = re.sub(r'page=\d+', f'page={page}', search_url_base)
    else:
        separator = "&" if "?" in search_url_base else "?"
        url = f"{search_url_base}{separator}page={page}"
    return url


class LinkedInScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LinkedIn Sales Navigator Scraper")
        self.root.geometry("800x600")
        
        # Configure logging
        logging.basicConfig(
            filename="scraper.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s: %(message)s"
        )
        
        # Variables
        self.search_url = tk.StringVar()
        self.start_page = tk.StringVar(value="1")
        self.end_page = tk.StringVar(value="1")
        self.wait_between_pages = tk.StringVar(value="5")
        self.wait_after_load = tk.StringVar(value="3")
        self.wait_after_scroll = tk.StringVar(value="3")
        self.save_format = tk.StringVar(value="csv")
        
        self.is_running = False
        self.driver = None
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # URL Input
        ttk.Label(main_frame, text="LinkedIn Sales Navigator Search URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.search_url, width=70).grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Basic Settings Frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="5")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Page Range
        ttk.Label(settings_frame, text="Start Page:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(settings_frame, textvariable=self.start_page, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(settings_frame, text="End Page:").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(settings_frame, textvariable=self.end_page, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(settings_frame, text="Save Format:").grid(row=0, column=4, sticky=tk.W)
        ttk.Radiobutton(settings_frame, text="CSV", variable=self.save_format, value="csv").grid(row=0, column=5)
        ttk.Radiobutton(settings_frame, text="Excel", variable=self.save_format, value="xlsx").grid(row=0, column=6)
        
        # Advanced Settings Frame
        advanced_frame = ttk.LabelFrame(main_frame, text="Advanced Settings", padding="5")
        advanced_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(advanced_frame, text="Wait Between Pages (s):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(advanced_frame, textvariable=self.wait_between_pages, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(advanced_frame, text="Wait After Load (s):").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(advanced_frame, textvariable=self.wait_after_load, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(advanced_frame, text="Wait After Scroll (s):").grid(row=0, column=4, sticky=tk.W)
        ttk.Entry(advanced_frame, textvariable=self.wait_after_scroll, width=10).grid(row=0, column=5, padx=5)
        
        # Progress Frame
        self.progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="5")
        self.progress_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, length=300, mode='determinate')
        self.progress_bar.grid(row=0, column=0, columnspan=2, pady=5, sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(self.progress_frame, text="Ready to start...")
        self.status_label.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.profiles_label = ttk.Label(self.progress_frame, text="Profiles found: 0")
        self.profiles_label.grid(row=2, column=0, columnspan=2, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="Start Scraping", command=self.start_scraping)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_scraping, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)
        
    def update_status(self, message, profiles_count=None):
        self.status_label.config(text=message)
        if profiles_count is not None:
            self.profiles_label.config(text=f"Profiles found: {profiles_count}")
        self.root.update()
        
    def update_progress(self, current, total):
        progress = (current - int(self.start_page.get()) + 1) / (int(self.end_page.get()) - int(self.start_page.get()) + 1) * 100
        self.progress_bar['value'] = progress
        self.root.update()
        
    def start_scraping(self):
        if not self.search_url.get():
            messagebox.showerror("Error", "Please enter a LinkedIn Sales Navigator search URL")
            return
            
        try:
            start_page = int(self.start_page.get())
            end_page = int(self.end_page.get())
            if start_page > end_page:
                messagebox.showerror("Error", "Start page cannot be greater than end page")
                return
        except ValueError:
            messagebox.showerror("Error", "Please enter valid page numbers")
            return
            
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Start scraping in a separate thread
        thread = threading.Thread(target=self.run_scraper)
        thread.daemon = True
        thread.start()
        
    def stop_scraping(self):
        self.is_running = False
        self.update_status("Stopping...")
        
    def run_scraper(self):
        try:
            self.update_status("Starting Chrome...")
            chrome_options = Options()
            chrome_options.add_argument("--force-device-scale-factor=1")
            chrome_options.add_argument("--high-dpi-support=1")
            chrome_options.add_argument("window-size=1366,768")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.maximize_window()
            
            self.update_status("Logging in to LinkedIn...")
            self.driver.get("https://www.linkedin.com/login/")
            
            lk_credentials = get_lk_credentials("./lk_credentials.json")
            enter_ids_on_lk_signin(self.driver, lk_credentials["email"], lk_credentials["password"])
            
            if "checkpoint/challenge" in self.driver.current_url:
                self.update_status("2FA required. Please complete verification in the browser...")
                messagebox.showinfo("2FA Required", "Please complete the two-factor authentication in the browser window and click OK when done.")
            
            search_url = self.search_url.get()
            start_page = int(self.start_page.get())
            end_page = int(self.end_page.get())
            
            total_info = []
            for page in range(start_page, end_page + 1):
                if not self.is_running:
                    break
                    
                self.update_status(f"Processing page {page} of {end_page}")
                self.update_progress(page, end_page)
                
                url = build_search_url(search_url, page)
                info = get_all_info_from_search_url(
                    self.driver,
                    url,
                    wait_after_page_loaded=int(self.wait_after_load.get()),
                    wait_after_scroll_down=int(self.wait_after_scroll.get())
                )
                total_info.extend(info)
                self.update_status(f"Completed page {page}", len(total_info))
                
                if page < end_page:
                    time.sleep(int(self.wait_between_pages.get()))
            
            if total_info:
                df = pd.DataFrame(total_info)
                df["linkedin_url"] = df.link_to_profile.apply(get_lk_url_from_sales_lk_url)
                
                if not os.path.exists("lksn_data"):
                    os.makedirs("lksn_data")
                    
                timestamp = str(int(time.time() * 1000))
                if self.save_format.get() == "csv":
                    filename = f"./lksn_data/{timestamp}_lk_salesnav_export.csv"
                    df.to_csv(filename, index=False)
                else:
                    filename = f"./lksn_data/{timestamp}_lk_salesnav_export.xlsx"
                    df.to_excel(filename, index=False)
                
                self.update_status(f"Data saved to {filename}", len(total_info))
                messagebox.showinfo("Success", f"Scraping completed! Data saved to {filename}")
            
        except Exception as e:
            logging.error("Error during scraping", exc_info=True)
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            
        finally:
            self.is_running = False
            if self.driver:
                self.driver.quit()
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.progress_bar['value'] = 0

if __name__ == "__main__":
    root = tk.Tk()
    app = LinkedInScraperGUI(root)
    root.mainloop()