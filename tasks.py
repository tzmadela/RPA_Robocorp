import os
import time
import logging
import csv
import re

from robocorp.tasks import task
from robocorp import workitems, browser
from bs4 import BeautifulSoup
from robocorp.workitems import Input

logging.basicConfig(level=logging.DEBUG)


class GothamistScraper:
    def __init__(self):
        self.browser = browser
        self.output_dir = os.getenv("OUTPUT_DIR", default="output")

    def initialize(self):
        self.browser.configure(slowmo=10)

    def scrape_news_articles(self, work_item: Input) -> None:
        try:
            if not work_item:
                raise ValueError("No work item provided.")

            search_term = work_item.payload.get("search_term")
            if not search_term:
                raise ValueError("No search term provided in the work item.")

            self.open_website()
            self.search_and_extract_news(search_term)
        except Exception as e:
            logging.exception("An error occurred during execution:")
            if work_item:
                work_item.fail(
                    exception_type='APPLICATION',
                    code='UNCAUGHT_ERROR',
                    message=str(e)
                )

    def open_website(self):
        logging.debug("Opening Gothamist website...")
        self.browser.goto("https://gothamist.com/")
        time.sleep(10)  # Wait for page to load

    def search_and_extract_news(self, search_term):
        page = self.browser.page()

        # Click the search button to reveal the search input
        logging.debug("Clicking search button...")
        search_button = page.query_selector('button[aria-label="Go to search page"]')
        if search_button:
            search_button.click()
            logging.debug("Search button clicked")
            time.sleep(5)

            # Input the search term
            logging.debug(f"Searching for: {search_term}")
            search_input = page.query_selector('input[name="q"]')
            if search_input:
                search_input.fill(search_term)
                logging.debug(f"Search term '{search_term}' filled")

                # Click the submit button to initiate the search
                submit_button = page.query_selector('button.search-page-button')
                if submit_button:
                    submit_button.click()
                    logging.debug("Search submitted")
                    time.sleep(10)  # Wait before starting scraping

                    # Extract news articles
                    self.extract_news_articles(page, search_term)

    def extract_news_articles(self, page, search_term):
        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        news_articles = soup.find_all("div", class_="v-card gothamist-card mod-horizontal mb-3 lg:mb-5 tag-small")

        logging.debug(f"Found {len(news_articles)} news articles")

        csv_filename = f"gothamist_news_{search_term.replace(' ', '_')}.csv"
        csv_filepath = os.path.join(self.output_dir, csv_filename)

        with open(csv_filepath, "w", newline="", encoding="utf-8") as csvfile:
            csv_writer = csv.writer(csvfile)
            headers = ["Title", "Date", "Description", "Image URL", "Title Count", "Description Count", "Contains Money"]
            csv_writer.writerow(headers)

            for index, article in enumerate(news_articles, start=1):
                title_element = article.find("div", class_="h2")
                title = title_element.get_text().strip() if title_element else "No title available"

                date_element = article.find("span", class_="article-item__date")
                date = date_element.get_text().strip() if date_element else "No date available"

                description_element = article.find("p", class_="desc")
                description = description_element.get_text().strip() if description_element else "No description available"

                image_element = article.find("img", class_="native-image")
                image_url = image_element["src"].strip() if image_element else ""

                title_count = self.count_occurrences(title, search_term)
                description_count = self.count_occurrences(description, search_term)
                contains_money = self.detect_money(title) or self.detect_money(description)

                csv_writer.writerow([title, date, description, image_url, title_count, description_count, contains_money])

    def count_occurrences(self, text, pattern):
        return len(re.findall(re.escape(pattern), text, re.IGNORECASE))

    def detect_money(self, text):
        money_patterns = r"\$\d+(\.\d+)?|\d+\s*dollars|\d+\s*USD"
        return bool(re.search(money_patterns, text, re.IGNORECASE))


scraper = GothamistScraper()


@task
def process_news_scraping():
    scraper.initialize()
    try:
        for work_item in workitems.inputs:
            scraper.scrape_news_articles(work_item)
    except Exception as err:
        logging.exception("An error occurred during task execution:")
        if workitems.inputs.current:
            workitems.inputs.current.fail(
                exception_type='APPLICATION',
                code='UNCAUGHT_ERROR',
                message=str(err)
            )


if __name__ == "__main__":
    process_news_scraping()
