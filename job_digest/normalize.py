"""Job normalization, text stripping, location cleaning, URL canonicalization, and regex extractors."""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from job_digest.models import Job, RawJob
from job_digest.profile import UserProfile

logger = logging.getLogger(__name__)

# Tracking parameters to strip from URLs
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "refid",
    "trackingid",
    "gh_jid",
    "src",
    "source",
    "fbclid",
    "gclid",
    "msclkid",
    "_hsenc",
    "_hsmi",
    "mc_cid",
    "mc_eid",
}

# Standard Indian location normalizations
LOCATION_MAPPINGS = [
    (re.compile(r"\b(gurgaon|gurugram)\b", re.I), "Gurugram"),
    (re.compile(r"\b(delhi\s*ncr|delhi-ncr|new\s+delhi|delhi)\b", re.I), "Delhi NCR"),
    (re.compile(r"\b(noida|greater\s+noida)\b", re.I), "Noida"),
    (re.compile(r"\b(bangalore|bengaluru)\b", re.I), "Bengaluru"),
    (re.compile(r"\b(bombay|mumbai)\b", re.I), "Mumbai"),
    (re.compile(r"\b(calcutta|kolkata)\b", re.I), "Kolkata"),
    (re.compile(r"\b(madras|chennai)\b", re.I), "Chennai"),
    (re.compile(r"\b(hyderabad)\b", re.I), "Hyderabad"),
    (re.compile(r"\b(pune)\b", re.I), "Pune"),
    (re.compile(r"\b(indore)\b", re.I), "Indore"),
    (re.compile(r"\b(remote|work\s+from\s+home|wfh|anywhere)\b", re.I), "Remote"),
]

# Extended tech skills catalog (~150 keywords)
EXTENDED_TECH_SKILLS = [
    "AWS", "GCP", "Docker", "Kubernetes", "Linux", "Git", "GitHub", "SQL",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Kafka",
    "Python", "FastAPI", "Django", "Flask", "JavaScript", "TypeScript", "React",
    "Next.js", "Vue", "Angular", "HTML", "CSS", "Tailwind CSS", "Node.js", "Express",
    "Java", "Spring Boot", "C++", "C#", ".NET", "Rust", "Golang", "Kotlin", "Swift",
    "Machine Learning", "AI", "NLP", "LLM", "Deep Learning", "Data Structures",
    "Algorithms", "pandas", "NumPy", "scikit-learn", "PyTorch", "TensorFlow",
    "REST API", "GraphQL", "Supabase", "Firebase", "Selenium", "Cypress", "Jest",
    "Pytest", "CI/CD", "DevOps", "Microservices", "OOP", "Tableau", "Power BI",
    "Excel", "Spark", "Hadoop", "Airflow", "Snowflake", "BigQuery", "OpenCV",
    "Keras", "Hugging Face", "LangChain", "LlamaIndex", "Celery", "RabbitMQ",
]


def clean_html_and_text(text_content: Optional[str]) -> str:
    """Strip HTML tags, unescape entities, and clean irregular whitespace."""
    if not text_content:
        return ""
    # Strip HTML tags
    no_html = re.sub(r"<[^>]+>", " ", text_content)
    # Decode HTML entities
    unescaped = html.unescape(no_html)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", unescaped).strip()
    return cleaned


def clean_location(raw_location: str) -> str:
    """Standardize city/regional location names."""
    if not raw_location or not raw_location.strip():
        return "Remote / India"

    loc = raw_location.strip()
    found_locations = []

    for pattern, normalized in LOCATION_MAPPINGS:
        if pattern.search(loc):
            if normalized not in found_locations:
                found_locations.append(normalized)

    if found_locations:
        return ", ".join(found_locations)

    return loc


def canonicalize_url(url: str) -> str:
    """Normalize URL by lowering netloc and removing marketing/tracking query parameters."""
    if not url:
        return ""

    parsed = urlparse(url.strip())
    query_params = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_params = [
        (k, v) for k, v in query_params if k.lower() not in TRACKING_PARAMS
    ]

    new_query = urlencode(filtered_params)
    clean_path = re.sub(r"/+", "/", parsed.path)
    if clean_path.endswith("/") and clean_path != "/":
        clean_path = clean_path.rstrip("/")

    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        clean_path,
        parsed.params,
        new_query,
        "",  # Drop fragment
    ))


def extract_skills(text_corpus: str, profile: Optional[UserProfile] = None) -> List[str]:
    """
    Extract skills using strict word-boundary matching.
    Guards against traps:
      - 'C': only matches in programming contexts (e.g. 'C/C++', 'C, C++', 'C programming', 'C language')
      - 'Go': only matches Golang or programming contexts (never 'go through', 'to go')
      - 'REST API': matches 'REST API', 'RESTful', etc. (never bare 'rest of')
    """
    if not text_corpus:
        return []

    matched_skills: Set[str] = set()

    # Trap: 'C' language detection
    if re.search(r"(?:\bC\s*\/\s*C\+\+|\bC\+\+\s*\/\s*C\b|\bC\s*,\s*C\+\+|\bC\s+or\s+C\+\+|\bC\s+(?:programming|language|code)\b)", text_corpus, re.I):
        matched_skills.add("C")

    # Trap: 'C++' detection (since '+' is non-word, use (?!\+) boundary)
    if re.search(r"\bC\+\+(?!\+)", text_corpus):
        matched_skills.add("C++")

    # Trap: 'Golang' / 'Go'
    if re.search(r"\b(?:golang|go\s+(?:programming|language|developer|code)|go\s*\/\s*python)\b", text_corpus, re.I):
        matched_skills.add("Go")

    # Trap: 'REST API' (never bare 'rest')
    if re.search(r"\b(?:rest\s*api|restful\s*api|restful|rest\s*apis|api\s*integration)\b", text_corpus, re.I):
        matched_skills.add("REST API")

    # Helper matcher for a keyword
    def match_word(word: str) -> bool:
        if word in ("C", "C++", "Go", "Golang", "REST API"):
            return False
        escaped = re.escape(word)
        return bool(re.search(rf"\b{escaped}\b", text_corpus, re.I))

    # 1. Profile skills and their aliases
    if profile:
        for skill in profile.skills:
            name = skill.name
            if name in matched_skills:
                continue

            if match_word(name):
                matched_skills.add(name)
                continue

            for alias in skill.aliases:
                if match_word(alias):
                    matched_skills.add(name)
                    break

    # 2. Extended catalog skills
    for ext_skill in EXTENDED_TECH_SKILLS:
        if ext_skill in matched_skills:
            continue
        if match_word(ext_skill):
            matched_skills.add(ext_skill)

    return sorted(list(matched_skills))


def parse_salary_and_stipend(text_corpus: str, is_intern: bool = False) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse salary and stipend across 4 common formats:
      1. Yearly LPA: '6-10 LPA', '3.5 LPA', '8 Lakhs', '5-7 Lakhs Per Annum'
      2. Absolute Yearly INR: '₹600,000 - ₹900,000 / year', '600000 - 800000 per annum'
      3. Monthly INR / Stipend: '₹25,000/month', '20k - 30k per month stipend', '30000 pm'
      4. USD foreign salary: '$40,000 - $60,000 / year', '$3,000/month'
    Returns (salary_lpa, stipend).
    """
    if not text_corpus:
        return None, None

    # Format 1: Explicit LPA / Lakhs per annum
    lpa_match = re.search(r"(?:₹|inr\s*)?(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lac|lakhs?|l)\b", text_corpus, re.I)
    if lpa_match:
        min_lpa = float(lpa_match.group(1))
        return min_lpa, None

    single_lpa = re.search(r"(?:₹|inr\s*)?(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?\s*(?:per\s*annum|\s*\/\s*yr|\s*\/\s*year)?)\b", text_corpus, re.I)
    if single_lpa:
        return float(single_lpa.group(1)), None

    # Format 2: Absolute Yearly INR (e.g. 600,000 to 900,000 per annum)
    abs_inr = re.search(r"(?:₹|inr|rs\.?)\s*(\d{1,3}(?:,\d{2,3})*|\d{5,8})\s*(?:-|to)\s*(?:₹|inr|rs\.?)?\s*(\d{1,3}(?:,\d{2,3})*|\d{5,8})\s*(?:per\s*(?:annum|year)|\s*\/\s*yr|\s*\/\s*year|pa)?", text_corpus, re.I)
    if abs_inr:
        val_str = abs_inr.group(1).replace(",", "")
        val = float(val_str)
        if val >= 100000:
            lpa = round(val / 100000.0, 2)
            return lpa, None

    # Single Absolute Yearly INR
    single_abs_inr = re.search(r"(?:₹|inr|rs\.?)\s*(\d{1,3}(?:,\d{2,3})*|\d{5,8})\s*(?:per\s*(?:annum|year)|\s*\/\s*yr|\s*\/\s*year|pa)\b", text_corpus, re.I)
    if single_abs_inr:
        val = float(single_abs_inr.group(1).replace(",", ""))
        if val >= 100000:
            return round(val / 100000.0, 2), None

    # Format 3: Monthly Salary / Stipend (₹25,000 / month, 20k-30k pm)
    monthly_match = re.search(
        r"(?:₹|inr|rs\.?)\s*(\d{1,3}(?:,\d{2,3})*|\d{4,6})\s*(?:-|to)?\s*(?:₹|inr|rs\.?)?\s*(\d{1,3}(?:,\d{2,3})*|\d{4,6})?\s*(?:per\s*month|\s*\/\s*month|\s*\/\s*pm|pm|stipend)",
        text_corpus,
        re.I,
    )
    if monthly_match:
        val1 = float(monthly_match.group(1).replace(",", ""))
        monthly_val = val1
        if is_intern or "stipend" in text_corpus.lower():
            return None, monthly_val
        else:
            # Full-time monthly converted to LPA
            annual_lpa = round((monthly_val * 12.0) / 100000.0, 2)
            return annual_lpa, None

    # Monthly in 'k' notation (e.g. 25k/month)
    k_match = re.search(r"(\d+)\s*k\s*(?:-|to)?\s*(\d+)?\s*k?\s*(?:per\s*month|\s*\/\s*month|\s*\/\s*pm|stipend)", text_corpus, re.I)
    if k_match:
        monthly_val = float(k_match.group(1)) * 1000.0
        if is_intern or "stipend" in text_corpus.lower():
            return None, monthly_val
        else:
            annual_lpa = round((monthly_val * 12.0) / 100000.0, 2)
            return annual_lpa, None

    # Format 4: USD foreign salary ($40,000 - $60,000 / year)
    usd_match = re.search(r"\$\s*(\d{1,3}(?:,\d{3})+|\d{4,6})\s*(?:-|to)?\s*\$?\s*(\d{1,3}(?:,\d{3})+|\d{4,6})?\s*(?:per\s*year|\s*\/\s*yr|\s*\/\s*year|annual)", text_corpus, re.I)
    if usd_match:
        usd_val = float(usd_match.group(1).replace(",", ""))
        # Convert USD to estimated LPA at 84 INR/USD
        lpa = round((usd_val * 84.0) / 100000.0, 2)
        return lpa, None

    return None, None


def detect_experience_and_batch(text_corpus: str, title: str) -> Tuple[Optional[float], bool, bool, List[int]]:
    """
    Detect minimum required experience (years), intern flag, apprentice flag, and graduation batch years.
    """
    combined = f"{title} {text_corpus}".lower()

    # Detect intern / apprentice
    is_intern = bool(re.search(r"\b(intern|internship|trainee\s+intern)\b", combined))
    is_apprentice = bool(re.search(r"\b(apprentice|apprenticeship)\b", combined))

    # Detect batch years (e.g. '2027 batch', 'batch of 2027', '2026/2027 passouts', '2027 graduates')
    batch_years: Set[int] = set()
    batch_matches = re.finditer(r"\b(202[0-9])\s*(?:batch|passout|pass\s*out|graduates?|passouts?)\b|\b(?:batch\s*(?:of)?|class\s*of)\s*(202[0-9])\b", combined)
    for m in batch_matches:
        year_str = m.group(1) or m.group(2)
        if year_str:
            batch_years.add(int(year_str))

    # Detect min experience years
    min_years: Optional[float] = None
    if bool(re.search(r"\b(fresher|freshers|entry\s+level|no\s+experience\s+required|0\s+years?)\b", combined)):
        min_years = 0.0
    else:
        # Check ranges like '0-2 years', '1-3 years', '2+ years'
        exp_range = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)(?:\s+of\s+experience)?", combined)
        if exp_range:
            min_years = float(exp_range.group(1))
        else:
            exp_single = re.search(r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)(?:\s+of\s+experience)?", combined)
            if exp_single:
                min_years = float(exp_single.group(1))

    return min_years, is_intern, is_apprentice, sorted(list(batch_years))


def normalize_raw_job(raw_job: RawJob, profile: Optional[UserProfile] = None) -> Job:
    """Normalize RawJob into fully enriched Job entity."""
    # Clean text and HTML
    description_cleaned = clean_html_and_text(raw_job.description_html or raw_job.description_text or "")
    combined_corpus = f"{raw_job.title} {description_cleaned}"

    # Clean location & canonical URL
    normalized_location = clean_location(raw_job.location)
    clean_url = canonicalize_url(raw_job.url)

    # Experience, intern/apprentice flags, batch years
    min_years, is_intern, is_apprentice, batch_years = detect_experience_and_batch(description_cleaned, raw_job.title)

    # Salary & Stipend
    salary_lpa, stipend = parse_salary_and_stipend(combined_corpus, is_intern=is_intern)

    # Extract skills
    skills = extract_skills(combined_corpus, profile=profile)

    return Job(
        title=clean_html_and_text(raw_job.title),
        company=raw_job.company.strip(),
        location=normalized_location,
        canonical_url=clean_url,
        description_text=description_cleaned,
        posted_at=raw_job.posted_at,
        source=raw_job.source,
        skills=skills,
        min_years=min_years,
        is_intern=is_intern,
        is_apprentice=is_apprentice,
        salary_lpa=salary_lpa,
        stipend=stipend,
        batch_years=batch_years,
        raw_data=raw_job.raw_data,
    )
