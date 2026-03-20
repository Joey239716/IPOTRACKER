# IPO Tracker

> A full-stack IPO hype tracking app — rebuilt with a better stack and full deployment.

IPO Tracker monitors upcoming and recent Initial Public Offerings by scraping S-1 filings directly from the SEC EDGAR database. It surfaces early IPO signals before they hit mainstream financial news, giving you a data edge on what companies are heading to market.

---

## Project Structure

```
IPOTRACKER/
├── client/          # Frontend (TypeScript)
├── server/          # Backend API (TypeScript)
└── worker/
    └── ipo-api/     # Data ingestion worker (Python)
```

The app follows a classic three-tier architecture:

- **Client** — UI for browsing and tracking IPOs
- **Server** — REST API serving IPO data to the client
- **Worker** — Python service that polls SEC EDGAR for new S-1 filings and feeds the backend

---

## Features

- **SEC EDGAR integration** — Fetches S-1 and S-1/A filings daily from the official SEC daily index
- **Company discovery** — Identifies new IPO candidates before they're widely covered
- **Date-range querying** — Pull filings across any date range with automatic weekend/holiday skipping
- **Direct SEC links** — Each result links directly to the filing on SEC.gov
- **Full-stack deployment** — Frontend, backend, and worker are all deployable together

---

## Tech Stack

| Layer    | Technology   |
|----------|--------------|
| Frontend | TypeScript   |
| Backend  | TypeScript (Node.js) |
| Worker   | Python       |
| Data Source | SEC EDGAR Daily Index |

---

## Getting Started

### Prerequisites

- Node.js (v18+)
- Python 3.9+
- npm or yarn

### Installation

**1. Clone the repo**
```bash
git clone https://github.com/Joey239716/IPOTRACKER.git
cd IPOTRACKER
```

**2. Install client dependencies**
```bash
cd client
npm install
```

**3. Install server dependencies**
```bash
cd ../server
npm install
```

**4. Install worker dependencies**
```bash
cd ../worker/ipo-api
pip install -r requirements.txt
```

### Running the App

**Start the server:**
```bash
cd server
npm run dev
```

**Start the client:**
```bash
cd client
npm run dev
```

**Run the IPO data worker:**
```bash
cd worker/ipo-api
python main.py
```

---

## How the Worker Works

The Python worker queries the **SEC EDGAR daily master index** for S-1 filings over a given date range:

```python
fetch_s1_filings("2025-01-01", "2025-03-31")
```

For each trading day in the range, it hits:
```
https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/master.{date}.idx
```

It filters for `S-1` form types, extracts the company name, CIK, filing date, and a direct link to the filing on SEC.gov. Weekends are automatically skipped. Any missed dates (non-weekend failures) are logged for retry.

---

## SEC Filing Types

| Form | Meaning |
|------|---------|
| S-1  | Initial IPO registration statement |
| S-1/A | Amendment to an S-1 filing |

---

## Roadmap

- [ ] Persistent database for filing storage (PostgreSQL / SQLite)
- [ ] Scheduled worker runs (cron / task queue)
- [ ] IPO hype scoring / ranking algorithm
- [ ] Email or webhook alerts for new S-1 filings
- [ ] Search and filter UI
- [ ] Historical IPO performance tracking

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## License

This project is open source. Check the repository for license details.

---

> Built by [Joey239716](https://github.com/Joey239716) — IPO Hype App, upgraded.
