import os
import logging
import asyncio
import time
from robocorp.tasks import task
from robocorp import browser, workitems
from bs4 import BeautifulSoup
import csv
import re
from robocorp.workitems import Input

logging.basicConfig(level=logging.DEBUG)

class GothamistScraper:
    def __init__(self):
        self.browser = browser
        self.output_dir = os.getenv("OUTPUT_DIR", default="output")
        os.makedirs(self.output_dir, exist_ok=True)  # Ensure the output directory exists

    def initialize(self):
        self.browser.configure(slowmo=10)

    async def scrape_news_articles(self, work_item: Input) -> None:
        if not work_item or not work_item.payload or "search_term" not in work_item.payload:
            logging.error("Invalid work item or no payload provided.")
            work_item.fail(
                exception_type='APPLICATION',
                code='INVALID_PAYLOAD',
                message='Invalid work item or no payload provided.'
            )
            return

        search_term = work_item.payload["search_term"]
        if not search_term:
            logging.error("No search term provided in the work item.")
            work_item.fail(
                exception_type='APPLICATION',
                code='MISSING_SEARCH_TERM',
                message='No search term provided in the work item.'
            )
            return

        try:
            self.open_website()
            await self.search_and_extract_news(search_term, work_item)
        except Exception as e:
            logging.exception("An error occurred during execution:")
            work_item.fail(
                exception_type='APPLICATION',
                code='UNCAUGHT_ERROR',
                message=str(e)
            )
        finally:
            self.browser.context().close()
            if work_item.status != 'failed' and work_item.status != 'done':
                work_item.done()

    def open_website(self):
        logging.debug("Opening Gothamist website...")
        self.browser.goto("https://gothamist.com/")
        time.sleep(10)  # Use regular time.sleep() for synchronous sleep

    async def search_and_extract_news(self, search_term, work_item: Input):
        page = self.browser.page()

        # Click the search button to reveal the search input
        logging.debug("Clicking search button...")
        search_button = await page.query_selector('button[aria-label="Go to search page"]')
        if search_button:
            await search_button.click()
            logging.debug("Search button clicked")
            await asyncio.sleep(5)  # Asynchronous sleep here

            # Input the search term
            logging.debug(f"Searching for: {search_term}")
            search_input = await page.query_selector('input[name="q"]')
            if search_input:
                await search_input.fill(search_term)
                logging.debug(f"Search term '{search_term}' filled")

                # Click the submit button to initiate the search
                submit_button = await page.query_selector('button.search-page-button')
                if submit_button:
                    await submit_button.click()
                    logging.debug("Search submitted")
                    await asyncio.sleep(10)  # Asynchronous sleep here

                    # Extract news articles
                    await self.extract_news_articles(page, search_term)

    async def extract_news_articles(self, page, search_term):
        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        news_articles = soup.find_all("div", class_="v-card gothamist-card mod-horizontal mb-3 lg:mb-5 tag-small")

        logging.debug(f"Found {len(news_articles)} news articles")

        csv_filename = f"gothamist_news_{search_term.replace(' ', '_')}.csv"
        csv_filepath = os.path.join(self.output_dir, csv_filename)

        try:
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
        except Exception as e:
            logging.exception(f"Error writing CSV file '{csv_filename}': {str(e)}")

    def count_occurrences(self, text, pattern):
        return len(re.findall(re.escape(pattern), text, re.IGNORECASE))

    def detect_money(self, text):
        money_patterns = r"\$\d+(\.\d+)?|\d+\s*dollars|\d+\s*USD"
        return bool(re.search(money_patterns, text, re.IGNORECASE))


scraper = GothamistScraper()

@task
async def process_news_scraping():
    scraper.initialize()
    try:
        tasks = [scraper.scrape_news_articles(work_item) for work_item in workitems.inputs]
        await asyncio.gather(*tasks)
    except Exception as err:
        print(err)
        workitems.inputs.current.fail(
            exception_type='APPLICATION',
            code='UNCAUGHT_ERROR',
            message=str(err)
        )

if __name__ == "__main__":
    asyncio.run(process_news_scraping())
