# LinkedIn Job Scraper

A fast Python CLI tool to scrape LinkedIn job postings and save them as JSON or Markdown files.

## Features

- Scrape single jobs or batch from URL list
- Export to JSON format (all jobs in one file)
- Export to Markdown with YAML frontmatter (one file per job)
- HTML to Markdown conversion preserves formatting (bold, lists, etc.)
- Browser reuse for fast batch processing (~1s per job)
- Customizable output directories

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

### Single Job

```bash
# JSON only (saved to ./output/jobs.json)
python -m src.main "https://linkedin.com/jobs/view/..."

# JSON + Markdown
python -m src.main "https://linkedin.com/jobs/view/..." -m

# Custom Markdown directory (e.g., Obsidian vault)
python -m src.main "https://linkedin.com/jobs/view/..." -m --md-dir ~/Documents/Jobs
```

### Batch Scraping

Create a file with URLs (one per line):

```
# jobs.txt - lines starting with # are ignored
https://linkedin.com/jobs/view/123456
https://linkedin.com/jobs/view/789012
https://linkedin.com/jobs/view/345678
```

Run batch scrape:

```bash
# Batch scrape with Markdown
python -m src.main --batch jobs.txt -m

# Batch with custom directories
python -m src.main --batch jobs.txt -m -o ./data --md-dir ~/Documents/Jobs
```

## CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `url` | Single LinkedIn job URL | - |
| `--batch FILE` | File with URLs (one per line) | - |
| `-m, --markdown` | Also create Markdown files | Off |
| `-o, --output` | JSON output directory | `./output` |
| `--md-dir` | Markdown output directory | Same as `-o` |
| `--no-headless` | Show browser window (debug) | Off |

## Output

### JSON (`output/jobs.json`)

All scraped jobs are saved to a single JSON file as an array:

```json
[
  {
    "id": "4335261686",
    "title": "AI Agent Engineer",
    "companyName": "Reavant",
    "location": "Amsterdam",
    "description": "...",
    ...
  }
]
```

### Markdown (`Title - Company.md`)

Each job gets its own Markdown file with YAML frontmatter:

```markdown
---
id: "4335261686"
title: "AI Agent Engineer"
companyName: "Reavant"
location: "Amsterdam"
...
---

**Job Description**

- Requirement 1
- Requirement 2
...
```

## Performance

| Mode | Time per job |
|------|--------------|
| Single job | ~2s |
| Batch (browser reuse) | ~1s |

## Extracted Fields

- Job ID, title, URL
- Company name, URL, ID
- Location
- Posted time & calculated publish date
- Number of applicants
- Full description (text + HTML)
- Contract type, experience level
- Job function, industry sector
- Apply type (Easy Apply / External)
- Poster name & profile URL

## License

MIT
