# LinkedIn Job Scraper

A Python CLI tool to scrape LinkedIn job postings and save them as JSON or Markdown files.

## Features

- Scrape job details from LinkedIn job URLs
- Export to JSON format
- Export to Markdown with YAML frontmatter
- Extracts: title, company, location, description, requirements, and more

## Installation

```bash
# Clone the repository
git clone https://github.com/karaoglusina/sina-linkedin-scraper.git
cd sina-linkedin-scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (one-time)
playwright install chromium
```

## Usage

```bash
# Scrape a job (JSON output)
python src/main.py "https://linkedin.com/jobs/view/..."

# Scrape with Markdown output
python src/main.py "https://linkedin.com/jobs/view/..." --markdown

# Specify output directory
python src/main.py "https://linkedin.com/jobs/view/..." -m -o ./my-jobs
```

## Output

- **JSON**: Saved to `output/jobs.json`
- **Markdown**: Saved to `output/<Job Title> <Company>.md`

## License

MIT
