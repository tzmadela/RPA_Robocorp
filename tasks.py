import os
import time
import logging
from robocorp.tasks import task
from robocorp import browser
from bs4 import BeautifulSoup
import csv
import re

logging.basicConfig(level=logging.DEBUG)


@task
def scrape_news_articles(search_term: str = "nyc") -> None:
    try:
        # Configure browser settings
        browser.configure(slowmo=10)

        # Open the Gothamist website
        open_website()

        # Perform search and extract news articles
        search_and_extract_news(search_term)

    except Exception as e:
        logging.exception("An error occurred during execution:")
    finally:
        # Close the browser context
        browser.context().close()


def open_website():
    logging.debug("Opening Gothamist website...")
    browser.goto("https://gothamist.com/")
    time.sleep(10)  # Wait for page to load


def search_and_extract_news(search_term):
    page = browser.page()

    # Click the search button to reveal the search input
    logging.debug("Clicking search button...")
    search_button = page.query_selector('button[aria-label="Go to search page"]')
    if search_button:
        search_button.click()
        logging.debug("Search button clicked")

    # Wait for a short interval after clicking the search button
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

    # Wait for a longer duration (e.g., 30 seconds) before starting scraping
    logging.debug("Waiting for 30 seconds before starting scraping...")
    time.sleep(30)

    # Extract news articles
    extract_news_articles(page, search_term)


def extract_news_articles(page, search_term):
    # Extract news articles
    html_content = page.content()
    soup = BeautifulSoup(html_content, "html.parser")
    news_articles = soup.find_all("div", class_="v-card gothamist-card mod-horizontal mb-3 lg:mb-5 tag-small")

    logging.debug(f"Found {len(news_articles)} news articles")

    # Create and open CSV file for writing
    csv_filename = "gothamist_news_data.csv"
    with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:
        csv_writer = csv.writer(csvfile)

        # Write headers to CSV file
        headers = ["Title", "Date", "Description", "Image URL", "Title Count", "Description Count", "Contains Money"]
        csv_writer.writerow(headers)

        # Iterate through news articles and extract information
        for index, article in enumerate(news_articles, start=1):
            title_element = article.find("div", class_="h2")
            title = title_element.get_text().strip() if title_element else "No title available"
            logging.debug(f"Extracted title: {title}")

            date_element = article.find("span", class_="article-item__date")
            date = date_element.get_text().strip() if date_element else "No date available"
            logging.debug(f"Extracted date: {date}")

            description_element = article.find("p", class_="desc")
            description = description_element.get_text().strip() if description_element else "No description available"
            logging.debug(f"Extracted description: {description}")

            image_element = article.find("img", class_="native-image")
            image_url = image_element["src"].strip() if image_element else ""
            logging.debug(f"Extracted image URL: {image_url}")

            # Capture screenshot of the image and save to file
            image_filename = f"image_{index}.png"
            capture_and_save_image(page, image_url, image_filename)

            title_count = count_occurrences(title, search_term)
            description_count = count_occurrences(description, search_term)
            contains_money = detect_money(title) or detect_money(description)

            # Write row to CSV file
            csv_writer.writerow([title, date, description, image_url, title_count, description_count, "True" if contains_money else "False"])


def capture_and_save_image(page, image_url, image_filename):
    # Capture screenshot of the image using its URL
    try:
        page.goto(image_url)
        page.capture_screenshot(image_filename)
    except Exception as e:
        logging.error(f"Error capturing image: {e}")


def count_occurrences(text, pattern):
    return len(re.findall(re.escape(pattern), text, re.IGNORECASE))


def detect_money(text):
    money_patterns = r"\$\d+(\.\d+)?|\d+\s*dollars|\d+\s*USD"
    return bool(re.search(money_patterns, text, re.IGNORECASE))


if __name__ == "__main__":
    # Specify the search term as a variable here (e.g., "NYC subway strike")
    search_term = "nyc"
    scrape_news_articles(search_term)
