"""Runtime configuration. Secrets are read from the environment and never logged."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

IST = timezone(timedelta(hours=5, minutes=30), name="IST")
REPO_ROOT = Path(__file__).resolve().parents[2]
PARSER_VERSION = "pypdf-pages-v4-discovery-rosters"
PROMPT_VERSION = "research-m1-v1.8"
SCHEMA_VERSION = "research-output-v1"


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    manifest_path: Path
    portfolio_path: Path
    frontend_dist: Path
    openai_api_key: Optional[str]
    openai_base_url: str
    model_primary: str
    model_primary_effort: str
    model_escalation: str
    model_escalation_effort: str
    max_download_bytes: int
    max_pdf_pages: int
    api_budget_usd: float
    job_budget_usd: float
    research_deadline_s: int
    model_provider: str = "openai"
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    gemini_api_key: Optional[str] = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "finn.sqlite3"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def model_configured(self) -> bool:
        key = {"anthropic": self.anthropic_api_key, "gemini": self.gemini_api_key}.get(self.model_provider, self.openai_api_key)
        return bool(key)

    @property
    def model_api_key_env(self) -> str:
        return {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}.get(self.model_provider, "OPENAI_API_KEY")


def get_settings() -> Settings:
    # Parse the local, ignored file as data; never source it as executable shell.
    # Existing environment settings take precedence. Secret values are not logged.
    load_dotenv(REPO_ROOT / ".env", override=False)
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None
    provider = (os.environ.get("FINN_MODEL_PROVIDER") or
                ("anthropic" if os.environ.get("ANTHROPIC_API_KEY")
                 else "gemini" if gemini_key else "openai")).lower()
    if provider not in ("openai", "anthropic", "gemini"):
        raise ValueError("FINN_MODEL_PROVIDER must be openai, anthropic or gemini")
    # Gemini's free tier (Google AI Studio) gives genuine synthesis at zero cost; its
    # OpenAI-compatible endpoint lets us reuse the same JSON-schema research contract.
    primary = {"anthropic": "claude-haiku-5-5", "gemini": "gemini-2.0-flash"}.get(provider, "gpt-6-luna")
    escalation = {"anthropic": "claude-sonnet-5-5", "gemini": "gemini-2.5-flash"}.get(provider, "gpt-6.1-sol")
    data_dir = Path(os.environ.get("FINN_DATA_DIR", REPO_ROOT / "data")).resolve()
    return Settings(
        data_dir=data_dir,
        manifest_path=Path(
            os.environ.get("FINN_REPLAY_MANIFEST", REPO_ROOT / "manifests" / "replay_2025_04.json")
        ).resolve(),
        portfolio_path=Path(
            os.environ.get("FINN_PORTFOLIO_MANIFEST", REPO_ROOT / "manifests" / "portfolio.json")
        ).resolve(),
        frontend_dist=Path(os.environ.get("FINN_FRONTEND_DIST", REPO_ROOT / "frontend" / "dist")).resolve(),
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        openai_base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        # Model choice follows the pre-build specification section 6; it is configurable
        # because runtime access has not been verified.
        model_primary=os.environ.get("FINN_MODEL_PRIMARY", primary),
        model_primary_effort=os.environ.get("FINN_MODEL_PRIMARY_EFFORT", "low"),
        model_escalation=os.environ.get("FINN_MODEL_ESCALATION", escalation),
        model_escalation_effort=os.environ.get("FINN_MODEL_ESCALATION_EFFORT", "medium"),
        max_download_bytes=int(os.environ.get("FINN_MAX_DOWNLOAD_BYTES", 50 * 1024 * 1024)),
        max_pdf_pages=int(os.environ.get("FINN_MAX_PDF_PAGES", 600)),
        api_budget_usd=_float("FINN_API_BUDGET_USD", 5.0),
        job_budget_usd=_float("FINN_JOB_BUDGET_USD", 0.25),
        research_deadline_s=int(os.environ.get("FINN_RESEARCH_DEADLINE_S", 180)),
        model_provider=provider,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        anthropic_base_url=_anthropic_base_url(),
        gemini_api_key=gemini_key,
        gemini_base_url=os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
    )


def _anthropic_base_url() -> str:
    """Resolve the Anthropic base URL, repairing a host-only override.

    The code posts to ``{base}/messages``, so the base must include the API version. Some
    shells (e.g. a coding-agent proxy) export ``ANTHROPIC_BASE_URL=https://api.anthropic.com``
    without the ``/v1`` segment; left as-is that would misroute every live call to
    ``/messages`` and 404. We append ``/v1`` for the official host when it is missing, while
    leaving a genuine custom proxy URL untouched.
    """
    from urllib.parse import urlparse
    url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
    parsed = urlparse(url)
    if parsed.hostname == "api.anthropic.com" and not re.search(r"/v\d+$", parsed.path or ""):
        url += "/v1"
    return url
