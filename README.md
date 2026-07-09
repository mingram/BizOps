# People Ops Command Center

A static, browser-based dashboard for recruiting and HR operations analytics. It consumes CSV data and offer-letter text files, computes metrics for pipeline health, headcount gaps, offer funnels, offer reconciliation, attrition, time-to-fill, cost analytics, and offer-decline analysis, then hydrates a standalone `index.html` that can be opened in any modern browser.

## Quick preview

The repository includes a pre-built dashboard in `dist/index.html`. Open it directly:

```bash
# macOS
open dist/index.html

# Linux
xdg-open dist/index.html

# Windows
start dist/index.html
```

Or serve the `dist/` directory with any static web server:

```bash
python3 -m http.server 8000 --directory dist
```

Then visit [http://localhost:8000](http://localhost:8000).

## Rebuild from source

### Prerequisites

- Python 3.8 or newer
- No third-party Python packages are required (only the standard library)

### Provide the dataset

The build pipeline expects the case dataset in a `data/` directory at the repository root:

```
data/
├── headcount_plan.csv
├── offer_log.csv
├── people_events.csv
├── recruiting_pipeline.csv
└── offer_letters/
    ├── C001.txt
    ├── C002.txt
    └── ...
```

The `data/` directory is gitignored, so it is not committed by default. If you want reviewers to be able to run the build, either place the dataset there before they clone the repo or commit it explicitly.

### Build the dashboard

```bash
python3 build.py
```

This runs `data_engine.py` to compute all metrics and writes a hydrated `dist/index.html` with the data embedded.

### Run the analytics scripts

Run the full analytics engine directly:

```bash
python3 data_engine.py
```

Run the recruiting risk utility:

```bash
python3 analyze_risk.py
```

## Project structure

- `build.py` — orchestrates the static site generation
- `data_engine.py` — pure Python analytics and data transformation module
- `dashboard.html` — dashboard template (contains `const DATA = null;` as a placeholder)
- `dist/index.html` — generated dashboard with computed data injected
- `analyze_risk.py` — CLI utility for identifying critical recruiting pipeline risks
- `data/` — input directory for CSVs and offer-letter text files (gitignored)

## Data schema

The expected CSV columns are:

- `headcount_plan.csv`: `department`, `level`, `approved_headcount`, `filled_seats`, `open_seats`, `priority`, `annual_budget_usd`
- `offer_log.csv`: `candidate_id`, `candidate_name`, `role`, `department`, `level`, `base_salary_usd`, `equity_grant_usd`, `signing_bonus_usd`, `bonus_target_usd`, `start_date`, `offer_status`, `decline_reason`, `competing_offer`, `days_to_close`
- `people_events.csv`: `employee_id`, `employee_name`, `department`, `manager`, `base_salary_usd`, `tenure_months`, `event_type`, `termination_reason`
- `recruiting_pipeline.csv`: `candidate_id`, `candidate_name`, `role`, `department`, `level`, `hiring_manager`, `source`, `current_stage`, `days_in_current_stage`, `disposition`, `time_to_close_days`
- `data/offer_letters/*.txt`: text files containing `Candidate ID`, `Base Salary`, `Equity Grant`, `Signing Bonus`, and `Start Date`

## Notes

- All Python code uses the standard library only; no `pip install` is needed.
- The dashboard is a single static HTML file with no backend or JavaScript build step.
- The `data/` directory is intentionally ignored; include the dataset in your submission only if you are allowed to share it.
