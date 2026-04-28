# 🛒 DealOrDud — Amazon Fake Discount Detector

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup4-Scraping-59666C?style=for-the-badge)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)
![Status](https://img.shields.io/badge/Status-Live-brightgreen?style=for-the-badge)

**Are Amazon India's "sale" discounts actually real?**
This project scrapes prices daily, builds a historical dataset from scratch,
and flags products where Amazon's displayed discount doesn't match reality.

[🚀 Live Dashboard](#) · [📊 View Dataset](#) · [📖 How It Works](#how-it-works)

</div>

---

## 📌 The Problem

Every Indian shopper has experienced this — you wait for the Big Billion Days sale, see a "67% off" badge, and rush to buy. But was the product genuinely cheaper?

Retailers often **quietly raise the MRP** a few weeks before a sale, then "discount" it back to the original price. The discount badge is real, but the saving isn't.

**This project detects exactly that.**

---

## 🎯 What This Project Does

```
Every morning at 6 AM IST (automatically, even when laptop is off):

  Amazon product pages
        ↓
  Scraper extracts: current price, MRP, displayed discount %
        ↓
  We independently compute the real discount %
        ↓
  Compare Amazon's claim vs our calculation
        ↓
  Flag products where the gap is ≥ 2 percentage points
        ↓
  Append to growing CSV dataset
        ↓
  Streamlit dashboard updates automatically
```

---

## 🔍 Key Findings

> *Updated as data collects over time*

| Metric | Value |
|---|---|
| Products tracked | 30+ across electronics, kitchen, fashion |
| Data collection started | April 2025 |
| Fake discounts detected | *updating* |
| Avg gap (displayed vs real) | *updating* |
| Most misleading category | *updating* |

---

## 🛠️ Tech Stack & Skills Demonstrated

| Area | Tools Used | What It Shows |
|---|---|---|
| **Web Scraping** | `requests`, `BeautifulSoup4` | Extract structured data from dynamic HTML |
| **Data Pipeline** | `csv`, `pandas` | Build a self-growing dataset from scratch |
| **Automation** | `schedule`, GitHub Actions | CI/CD, cloud scheduling, cron jobs |
| **Data Analysis** | `pandas`, statistical thresholds | Anomaly detection, comparative analysis |
| **Visualisation** | `Streamlit`, `Plotly` | Interactive dashboards, data storytelling |
| **Engineering** | Retry logic, multi-selector fallback, session management | Production-style scraping patterns |

---

## 🏗️ Project Structure

```
fake-discount-detector/
│
├── scraper.py                     # Main scraper — fetches & analyses prices
├── automation.py                  # Runs scraper daily on local machine
├── app.py                         # Streamlit interactive dashboard
├── requirements.txt               # Python dependencies
│
├── products.csv                   # Auto-discovered product list
│
├── data/
|--price_history.csv               # Growing price history dataset
│
├── .github/
│   └── workflows/
│       └── scrape.yml             # GitHub Actions — cloud automation
│
└── README.md
```

---

## ⚙️ How It Works

### Step 1 — Product Discovery (Automatic)
The scraper visits Amazon India's bestseller and deals pages, extracts all product ASINs from page links, and saves them to `products.csv`. No manual URL copying needed.

### Step 2 — Price Extraction (Multi-Strategy)
Amazon frequently changes its HTML layout. Our scraper uses **4 extraction strategies** in sequence:

```
Strategy A → CSS selectors (9 selectors per field)
Strategy B → Embedded JavaScript JSON data
Strategy C → Regex on script tags
Strategy D → Smart fallback (collects all prices, picks lowest below MRP)
```

This layered approach means if Amazon changes one layout, the others still work.

### Step 3 — Fake Discount Detection
```python
# We compute the real discount independently
computed_pct = ((mrp - current_price) / mrp) * 100

# Compare with what Amazon claims
gap = abs(amazon_displayed_pct - computed_pct)

# Flag if gap is 2 percentage points or more
is_fake = gap >= 2
```

A product showing "67% off" that we compute as "3% off" gets flagged with note: `gap_of_64.0_pct_points`.

### Step 4 — Automated Daily Collection
GitHub Actions runs `scraper.py` every morning at 6 AM IST on a free cloud server. The updated CSV is committed back to this repository automatically — no laptop needed.

---

## 📊 Sample Output

```
══════════════════════════════════════════════════════════
  DealOrDud — Amazon Fake Discount Detector
  Started: 2025-04-29 06:00:01
══════════════════════════════════════════════════════════

  [1/25] boAt Rockerz 450 Pro Bluetooth Headphones
    ✓ OK   | Price:  ₹1,299 | MRP:  ₹3,990 | Amazon: 67% | We compute: 67.4% | discount_looks_genuine

  [2/25] ZEBRONICS Type C to Type C Braided Cable 60W
    ⚠ FAKE | Price:    ₹299 | MRP:    ₹999 | Amazon: 83% | We compute:  7.1% | gap_of_75.9_pct_points

  [3/25] Noise ColorFit Pro 4 Smartwatch
    ✓ OK   | Price:  ₹1,799 | MRP:  ₹6,999 | Amazon: 74% | We compute: 74.3% | discount_looks_genuine
```

---

## 🚀 Run It Yourself

### Prerequisites
```bash
pip install requests beautifulsoup4 streamlit plotly pandas
```

### First run (auto-discovers products)
```bash
python scraper.py
```

### Run the dashboard
```bash
streamlit run app.py
```

### Set up daily automation (laptop must stay on)
```bash
python automation.py
```

### Set up cloud automation (runs even when laptop is off)
Push `.github/workflows/scrape.yml` to your GitHub repo — GitHub handles the rest.

---

## 📈 Dataset Schema

Each row in `amazon_discount_history.csv` represents one product scraped on one day:

| Column | Description | Example |
|---|---|---|
| `scraped_at` | Timestamp of collection | `2025-04-29 06:00:01` |
| `date` | Date only | `2025-04-29` |
| `asin` | Amazon product ID | `B08N5WRWNW` |
| `product_name` | Full product title | `boAt Rockerz 450 Pro` |
| `current_price` | Today's selling price | `1299.0` |
| `mrp` | Original/MRP price | `3990.0` |
| `displayed_discount_pct` | Amazon's claimed discount | `67.0` |
| `computed_discount_pct` | Our calculated discount | `67.46` |
| `fake_discount` | Flagged as misleading | `False` |
| `analysis_note` | Reason for flag or clear | `discount_looks_genuine` |

---

## 🧠 What I Learned Building This

- **Web scraping is not just `requests.get()`** — production scrapers need session management, retry logic, rotating headers, cookie handling, and multi-strategy fallbacks
- **Data is never where you expect it** — Amazon hides prices in HTML, in JavaScript objects, in JSON-LD structured data, and in script tags. You have to check all of them
- **Defining "fake" is a data decision** — I chose a 2% threshold after testing; too strict gives false positives, too loose misses real manipulation
- **Automation architecture matters** — local `schedule` works for development; GitHub Actions handles production with zero cost

---

## ⚠️ Disclaimer

This project is built for **educational and portfolio purposes**. Scraping is done at a low, respectful rate (4–9 second delays between requests) to avoid server load. All data is from publicly accessible Amazon India pages.

---

## 👩‍💻 Author

**Anshika Goyal**
B.Tech 2nd Year | Aspiring Data Analyst

[![GitHub](https://img.shields.io/badge/GitHub-AnshikaGoyal17-181717?style=flat&logo=github)](https://github.com/AnshikaGoyal17)

---

<div align="center">

*If this project helped you or you found a fake discount — give it a ⭐*

</div>