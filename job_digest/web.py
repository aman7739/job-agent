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

import yaml

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
from job_digest.profile import load_profile
from job_digest.profile_service import get_active_profile_from_db, save_profile_to_db
from job_digest.status import (
    add_manual_job,
    get_job_status,
    get_weekly_applied_count,
    set_job_status,
)

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

    weekly_cnt = get_weekly_applied_count(session) if session else 0

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
            "weekly_applied_count": weekly_cnt,
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

    weekly_cnt = get_weekly_applied_count(session) if session else 0

    return templates.TemplateResponse(
        request=request,
        name="web/history.html",
        context={
            "active_page": "history",
            "is_authenticated": True,
            "jobs": jobs_list,
            "weekly_applied_count": weekly_cnt,
            "filters": {
                "section": section,
                "min_score": min_score,
                "location": location,
                "source": source,
                "status": status_filter,
            },
        },
    )


# ==============================================================================
# Job Status Actions
# ==============================================================================

@app.post("/jobs/{fingerprint}/status")
async def update_job_status_route(
    request: Request,
    fingerprint: str,
    status: str = Form(...),
    notes: Optional[str] = Form(None),
    user: str = Depends(require_auth),
    session: Optional[Session] = Depends(get_db),
):
    """Update application status (saved, applied, not_interested, seen)."""
    if session:
        try:
            set_job_status(session, fingerprint, status, notes=notes)
        except Exception as exc:
            logger.warning(f"Error updating status for {fingerprint}: {exc}")

    referer = request.headers.get("referer")
    redirect_target = referer if referer and "/login" not in referer else "/history"
    return RedirectResponse(url=redirect_target, status_code=303)


# ==============================================================================
# Profile & Match Settings Editor
# ==============================================================================

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    success: Optional[str] = None,
    error: Optional[str] = None,
    user: str = Depends(require_auth),
    session: Optional[Session] = Depends(get_db),
):
    """Render profile settings editor."""
    profile = load_profile(session=session)
    active_version = 1
    profile_yaml_str = ""

    if session:
        try:
            row = session.execute(
                text("SELECT version, profile_yaml FROM user_profiles WHERE is_active = TRUE ORDER BY version DESC LIMIT 1")
            ).fetchone()
            if row:
                active_version = row[0]
                profile_yaml_str = row[1]
        except Exception as exc:
            logger.warning(f"Error querying active profile version: {exc}")

    if not profile_yaml_str:
        profile_yaml_str = yaml.dump(profile.model_dump(mode="json"), sort_keys=False)

    weekly_cnt = get_weekly_applied_count(session) if session else 0

    return templates.TemplateResponse(
        request=request,
        name="web/settings.html",
        context={
            "active_page": "settings",
            "is_authenticated": True,
            "profile": profile,
            "active_version": active_version,
            "profile_yaml": profile_yaml_str,
            "weekly_applied_count": weekly_cnt,
            "success": success,
            "error": error,
        },
    )


@app.post("/settings", response_class=HTMLResponse)
async def update_settings_route(
    request: Request,
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    min_score: Optional[float] = Form(None),
    strong_threshold: Optional[float] = Form(None),
    company_blocklist: Optional[str] = Form(None),
    exclude_title_words: Optional[str] = Form(None),
    channels: Optional[List[str]] = Form(None),
    raw_yaml: Optional[str] = Form(None),
    user: str = Depends(require_auth),
    session: Optional[Session] = Depends(get_db),
):
    """Save updated profile version to database."""
    if not session:
        raise HTTPException(status_code=500, detail="Database session not available.")

    current_profile = load_profile(session=session)

    try:
        # Check if direct raw YAML was provided
        if raw_yaml and raw_yaml.strip() and raw_yaml.strip() != "None" and "version:" in raw_yaml:
            updated_profile, new_version = save_profile_to_db(session, raw_yaml.strip())
        else:
            prof_dict = current_profile.model_dump(mode="json")
            if name:
                prof_dict["user"]["name"] = name.strip()
            if email:
                prof_dict["user"]["email"] = email.strip()
            if min_score is not None:
                prof_dict["scoring"]["min_score"] = float(min_score)
            if strong_threshold is not None:
                prof_dict["scoring"]["strong_threshold"] = float(strong_threshold)
            if company_blocklist is not None:
                prof_dict["hard_filters"]["company_blocklist"] = [
                    c.strip().lower() for c in company_blocklist.split(",") if c.strip()
                ]
            if exclude_title_words is not None:
                prof_dict["hard_filters"]["exclude_title_words"] = [
                    w.strip().lower() for w in exclude_title_words.split(",") if w.strip()
                ]
            if channels:
                prof_dict["digest"]["channels"] = channels

            new_yaml = yaml.dump(prof_dict, sort_keys=False)
            updated_profile, new_version = save_profile_to_db(session, new_yaml)

        return RedirectResponse(
            url=f"/settings?success=Profile+version+{new_version}+saved+successfully.+Takes+effect+on+tomorrow%27s+run.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        logger.warning(f"Error saving profile settings: {exc}")
        weekly_cnt = get_weekly_applied_count(session) if session else 0
        return templates.TemplateResponse(
            request=request,
            name="web/settings.html",
            context={
                "active_page": "settings",
                "is_authenticated": True,
                "profile": current_profile,
                "active_version": 1,
                "profile_yaml": raw_yaml or "",
                "weekly_applied_count": weekly_cnt,
                "success": None,
                "error": f"Failed to save settings: {exc}",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# ==============================================================================
# Source Health Page
# ==============================================================================

@app.get("/sources", response_class=HTMLResponse)
async def source_health_page(
    request: Request,
    user: str = Depends(require_auth),
    session: Optional[Session] = Depends(get_db),
):
    """Render source health monitoring page across all 8 permitted source adapters."""
    all_source_names = [
        "greenhouse", "lever", "ashby", "smartrecruiters",
        "workable", "adzuna", "remotive", "email_alerts",
    ]
    sources_metrics: List[Dict[str, Any]] = []

    if session:
        for sname in all_source_names:
            try:
                row = session.execute(
                    text(
                        """
                        SELECT started_at, jobs_found, is_success, error_message
                        FROM source_runs
                        WHERE source_name = :name
                        ORDER BY started_at DESC LIMIT 1
                        """
                    ),
                    {"name": sname},
                ).fetchone()
                if row:
                    last_run = row[0].strftime("%d %b %Y %H:%M UTC") if hasattr(row[0], "strftime") else str(row[0])
                    sources_metrics.append({
                        "name": sname,
                        "last_run": last_run,
                        "jobs_found": row[1],
                        "is_success": bool(row[2]),
                        "error_message": row[3],
                    })
                else:
                    sources_metrics.append({
                        "name": sname,
                        "last_run": None,
                        "jobs_found": 0,
                        "is_success": False,
                        "error_message": "No run recorded yet",
                    })
            except Exception as exc:
                sources_metrics.append({
                    "name": sname,
                    "last_run": None,
                    "jobs_found": 0,
                    "is_success": False,
                    "error_message": str(exc),
                })
    else:
        for sname in all_source_names:
            sources_metrics.append({
                "name": sname,
                "last_run": "Offline",
                "jobs_found": 0,
                "is_success": True,
                "error_message": None,
            })

    weekly_cnt = get_weekly_applied_count(session) if session else 0

    return templates.TemplateResponse(
        request=request,
        name="web/sources.html",
        context={
            "active_page": "sources",
            "is_authenticated": True,
            "sources": sources_metrics,
            "weekly_applied_count": weekly_cnt,
        },
    )


# ==============================================================================
# Manual Add Job Form
# ==============================================================================

@app.get("/jobs/add", response_class=HTMLResponse)
async def add_job_page(
    request: Request,
    error: Optional[str] = None,
    user: str = Depends(require_auth),
    session: Optional[Session] = Depends(get_db),
):
    """Render manual add-a-job form."""
    weekly_cnt = get_weekly_applied_count(session) if session else 0
    return templates.TemplateResponse(
        request=request,
        name="web/add_job.html",
        context={
            "active_page": "add_job",
            "is_authenticated": True,
            "weekly_applied_count": weekly_cnt,
            "error": error,
        },
    )


@app.post("/jobs/add")
async def add_job_action(
    request: Request,
    title: str = Form(...),
    company: str = Form(...),
    location: str = Form(...),
    canonical_url: str = Form(...),
    description_text: str = Form(""),
    salary_lpa: Optional[float] = Form(None),
    stipend: Optional[float] = Form(None),
    is_intern: Optional[bool] = Form(False),
    user: str = Depends(require_auth),
    session: Optional[Session] = Depends(get_db),
):
    """Manually add an opportunity and score against active profile."""
    if not session:
        raise HTTPException(status_code=500, detail="Database session not available.")

    profile = load_profile(session=session)
    try:
        add_manual_job(
            session=session,
            profile=profile,
            title=title,
            company=company,
            location=location,
            canonical_url=canonical_url,
            description_text=description_text,
            salary_lpa=salary_lpa,
            stipend=stipend,
            is_intern=bool(is_intern),
        )
        return RedirectResponse(url="/history?status=saved", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        logger.warning(f"Error adding manual job: {exc}")
        return RedirectResponse(url=f"/jobs/add?error={exc}", status_code=status.HTTP_303_SEE_OTHER)

