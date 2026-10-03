# Job Digest Agent

Personal automated job digest for freshers, internships, and apprenticeships. Fetches openings from permitted ATS and search APIs, normalizes, deduplicates, scores based on profile alignment, and delivers daily morning digests via Telegram and Email.

## Quick Start

### 1. Prerequisites
- Python 3.12+
- Git

### 2. Environment Setup
```bash
# Clone the repository
git clone <repo_url>
cd "AI AGENT"

# Create virtual environment
py -3.12 -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Tests
```bash
pytest -v
```
