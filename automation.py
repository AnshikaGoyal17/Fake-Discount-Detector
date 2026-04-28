# automation.py
# Project : DealOrDud — Fake Discount Detector
# Purpose : Run the scraper automatically every day at a set time

import schedule
import time
import logging
from datetime import datetime
from scraper import run_scraper

logging.basicConfig(
    filename="scraper_log.txt",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    filemode="a",
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

def scheduled_job():
    logging.info("Scheduled scrape starting...")
    try:
        run_scraper()
        logging.info("Scrape completed successfully.")
    except Exception as e:
        logging.error(f"Scrape failed: {e}")

schedule.every().day.at("10:00").do(scheduled_job)

print("\n" + "=" * 55)
print("  DealOrDud — Daily Price Tracker")
print("  Automation Started")
print("=" * 55)
print(f"  Started at   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Daily scrape : 10:00 AM every day")
print(f"  Logs saved to: scraper_log.txt")
print(f"  Data saved to: price_history.csv")
print("=" * 55)

print("  Running initial scrape now to confirm everything works...")
scheduled_job()

print(f"\n  Next scheduled scrape: tomorrow at 10:00 AM")
print("  Press Ctrl+C to stop\n")

while True:
    schedule.run_pending()   # check if any job is due
    time.sleep(60)           # wait 60 seconds before checking again