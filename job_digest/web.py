"""FastAPI web dashboard for Job Digest Agent with single-user authentication and job history."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from job_digest.auth import (
    check_rate_limit,
    create_session_token,
    get_configured_password_hash,
    get_current_user_from_request,
    record_failed_attempt,
    require_auth,
    reset_rate_limit,
    verify_password,
)
from job_digest.db import get_database_url, get_db_session

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(
    title="Job Digest Agent Dashboard",
    description="Private Single-User Dashboard for daily job digest and application tracking",
    docs_url=None,  # Disabled for privacy
    redoc_url=None,
)


def get_db():
    """Dependency yielding a database session if configured."""
    if not get_database_url():
        yield None
        return

    session_ctx = get_db_session()
    with session_ctx as session:
        yield session


def get_client_ip(request: Request) -> str:
    """Extract client IP handling proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


# ==============================================================================
# Authentication Routes
# ==============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: Optional[str] = None):
    """Render single-user password login page."""
    user = get_current_user_from_request(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="web/login.html",
        context={
            "next_url": next or "/",
            "error": None,
            "is_authenticated": False,
        },
    )


@app.post("/login", response_class=HTMLResponse)
async def login_action(
    request: Request,
    password: str = Form(...),
    next: Optional[str] = Form("/"),
):
    """Process login with Argon2 verification and rate limiting."""
    client_ip = get_client_ip(request)

    # 1. Check rate limit
    if not check_rate_limit(client_ip):
        logger.warning(f"Login rate limit exceeded for IP: {client_ip}")
        return templates.TemplateResponse(
            request=request,
            name="web/login.html",
            context={
                "next_url": next,
                "error": "Too many failed attempts. Please wait 5 minutes before trying again.",
                "is_authenticated": False,
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # 2. Verify password against configured Argon2 hash
    config_hash = get_configured_password_hash()
    is_valid = verify_password(password, config_hash)

    if not is_valid:
        record_failed_attempt(client_ip)
        logger.warning(f"Failed login attempt from IP: {client_ip}")
        return templates.TemplateResponse(
            request=request,
            name="web/login.html",
            context={
                "next_url": next,
                "error": "Invalid master password. Please try again.",
                "is_authenticated": False,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 3. Success: reset rate limit & set session cookie
    reset_rate_limit(client_ip)
    token = create_session_token("admin")

    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    redirect_url = next if next and next.startswith("/") else "/"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_https,
        max_age=604800,  # 7 days
    )
    logger.info(f"Successful login from IP: {client_ip}")
    return response


@app.post("/logout")
@app.get("/logout")
async def logout_action():
    """Clear session cookie and redirect to login."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    return response


# ==============================================================================
# Protected Pages: Today's Digest & Job History
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def today_digest_page(
    request: Request,
    user: str = Depends(require_auth),
    session: Optional[Session] = Depends(get_db),
):
    """Render today's latest job digest."""
    digest_row = None
    if session:
        try:
            digest_row = session.execute(
                text(
                    """
                    SELECT sent_at, total_jobs, internships_count, fulltime_count,
                           channels_notified, failed_sources, content_html
                    FROM digests
                    ORDER BY sent_at DESC
                    LIMIT 1
                    """
                )
            ).fetchone()
        except Exception as exc:
            logger.warning(f"Error fetching latest digest from DB: {exc}")

    if digest_row:
        sent_at, total_jobs, intern_cnt, ft_cnt, channels, failed_srcs, html_content = digest_row
        date_str = sent_at.strftime("%A, %d %B %Y") if hasattr(sent_at, "strftime") else str(sent_at)
        failed_list = list(failed_srcs) if failed_srcs else []
        is_empty = total_jobs == 0
        digest_html_body = html_content or ""
        new_count = total_jobs
        seen_count = 0
    else:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%A, %d %B %Y")
        total_jobs = 0
        intern_cnt = 0
        ft_cnt = 0
        failed_list = []
        is_empty = True
        digest_html_body = ""
        new_count = 0
        seen_count = 0

    return templates.TemplateResponse(
        request=request,
        name="web/digest_view.html",
        context={
            "active_page": "digest",
            "is_authenticated": True,
            "digest_date": date_str,
            "total_jobs": total_jobs,
            "new_count": new_count,
            "seen_count": seen_count,
            "internships_count": intern_cnt,
            "fulltime_count": ft_cnt,
            "failed_sources": failed_list,
            "is_empty": is_empty,
            "digest_html_body": digest_html_body,
        },
    )


@app.get("/history", response_class=HTMLResponse)
async def job_history_page(
    request: Request,
    section: str = "all",
    min_score: float = 0.0,
    location: str = "",
    source: str = "all",
    status_filter: str = "all",
    user: str = Depends(require_auth),
    session: Optional[Session] = Depends(get_db),
):
    """
    Render job history page with multi-criteria filtering:
    section (internships vs fulltime), score, location, source, and status.
    """
    jobs_list: List[Dict[str, Any]] = []

    if session:
        try:
            query = """
                SELECT j.fingerprint, j.title, j.company, j.location, j.canonical_url,
                       j.salary_lpa, j.stipend, j.is_intern, j.is_apprentice, j.score,
                       j.source, j.posted_at, s.status, s.saved_at, s.applied_at
                FROM seen_jobs s
                JOIN jobs j ON s.fingerprint = j.fingerprint
                WHERE 1=1
            """
            params: Dict[str, Any] = {}

            if section == "internships":
                query += " AND (j.is_intern = 1 OR j.is_apprentice = 1)"
            elif section == "fulltime":
                query += " AND (j.is_intern = 0 AND j.is_apprentice = 0)"

            if min_score > 0.0:
                query += " AND j.score >= :min_score"
                params["min_score"] = min_score

            if location.strip():
                query += " AND LOWER(j.location) LIKE :loc"
                params["loc"] = f"%{location.strip().lower()}%"

            if source != "all":
                query += " AND j.source = :source"
                params["source"] = source

            if status_filter != "all":
                query += " AND s.status = :status"
                params["status"] = status_filter

            query += " ORDER BY j.score DESC, s.last_seen_at DESC LIMIT 100"

            rows = session.execute(text(query), params).fetchall()
            for r in rows:
                jobs_list.append(
                    {
                        "fingerprint": r[0],
                        "title": r[1],
                        "company": r[2],
                        "location": r[3],
                        "canonical_url": r[4],
                        "salary_lpa": float(r[5]) if r[5] is not None else None,
                        "stipend": float(r[6]) if r[6] is not None else None,
                        "is_intern": bool(r[7]),
                        "is_apprentice": bool(r[8]),
                        "score": float(r[9]) if r[9] is not None else None,
                        "source": r[10],
                        "posted_at": r[11],
                        "status": r[12],
                        "saved_at": r[13],
                        "applied_at": r[14],
                    }
                )
        except Exception as exc:
            logger.warning(f"Error querying job history: {exc}")

    return templates.TemplateResponse(
        request=request,
        name="web/history.html",
        context={
            "active_page": "history",
            "is_authenticated": True,
            "jobs": jobs_list,
            "filters": {
                "section": section,
                "min_score": min_score,
                "location": location,
                "source": source,
                "status": status_filter,
            },
        },
    )
