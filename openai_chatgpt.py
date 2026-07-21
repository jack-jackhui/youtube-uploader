"""LLM routing for video topic generation.

Direct Google Gemini is the primary provider. Cloudflare Workers AI is the
first fallback, followed by OpenRouter models in their configured order. The
chain advances only for provider/auth/quota/model/transport failures. Each
provider is attempted once; malformed application requests (HTTP 400/422) do
not fall through to another provider.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from openai import OpenAI


DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_CLOUDFLARE_WORKERS_AI_MODEL = "@cf/qwen/qwen3-30b-a3b-fp8"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODELS = (
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
)
RETRYABLE_HTTP_STATUSES = {401, 403, 404, 408, 409, 425, 429}
NON_RETRYABLE_HTTP_STATUSES = {400, 422}


@dataclass(frozen=True)
class LLMProvider:
    name: str
    model: str
    base_url: str
    api_key: str


def _read_secret(value_var: str, file_var: str) -> Optional[str]:
    """Read a credential from an environment value or a referenced file."""
    direct_value = os.getenv(value_var, "").strip()
    if direct_value:
        return direct_value

    secret_path = os.getenv(file_var, "").strip()
    if not secret_path:
        return None
    try:
        value = Path(secret_path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def build_provider_chain() -> List[LLMProvider]:
    """Build Gemini -> Workers AI -> OpenRouter in deterministic order."""
    providers: List[LLMProvider] = []

    gemini_key = _read_secret("GEMINI_API_KEY", "GEMINI_API_KEY_FILE")
    if gemini_key:
        providers.append(
            LLMProvider(
                name="gemini",
                model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
                or DEFAULT_GEMINI_MODEL,
                base_url=os.getenv("GEMINI_BASE_URL", DEFAULT_GEMINI_BASE_URL).strip()
                or DEFAULT_GEMINI_BASE_URL,
                api_key=gemini_key,
            )
        )

    cloudflare_key = _read_secret(
        "CLOUDFLARE_WORKERS_AI_API_KEY",
        "CLOUDFLARE_WORKERS_AI_API_KEY_FILE",
    )
    cloudflare_account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    cloudflare_base_url = os.getenv(
        "CLOUDFLARE_WORKERS_AI_BASE_URL", ""
    ).strip()
    if not cloudflare_base_url and cloudflare_account_id:
        cloudflare_base_url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{cloudflare_account_id}/ai/v1"
        )
    if cloudflare_key and cloudflare_base_url:
        providers.append(
            LLMProvider(
                name="cloudflare_workers_ai",
                model=os.getenv(
                    "CLOUDFLARE_WORKERS_AI_MODEL",
                    DEFAULT_CLOUDFLARE_WORKERS_AI_MODEL,
                ).strip()
                or DEFAULT_CLOUDFLARE_WORKERS_AI_MODEL,
                base_url=cloudflare_base_url,
                api_key=cloudflare_key,
            )
        )

    openrouter_key = _read_secret("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_FILE")
    configured_models = os.getenv("OPENROUTER_MODELS", ",".join(DEFAULT_OPENROUTER_MODELS))
    openrouter_models = [model.strip() for model in configured_models.split(",") if model.strip()]
    if openrouter_key:
        base_url = os.getenv("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL).strip()
        for model in openrouter_models:
            providers.append(
                LLMProvider(
                    name="openrouter",
                    model=model,
                    base_url=base_url or DEFAULT_OPENROUTER_BASE_URL,
                    api_key=openrouter_key,
                )
            )

    return providers


def _status_code(exc: Exception) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _is_retryable_provider_error(exc: Exception) -> bool:
    status = _status_code(exc)
    if status in NON_RETRYABLE_HTTP_STATUSES:
        return False
    if status in RETRYABLE_HTTP_STATUSES or (status is not None and status >= 500):
        return True

    # The OpenAI SDK's transport errors have no HTTP status. Restrict fallback
    # to its provider/connection exception family rather than arbitrary bugs.
    return exc.__class__.__module__.startswith("openai")


def generate_with_provider_chain(
    prompt: str,
    providers: Optional[Iterable[LLMProvider]] = None,
    client_factory: Callable[..., OpenAI] = OpenAI,
) -> str:
    """Generate one title using a bounded provider chain.

    Raises the original error when it is not eligible for fallback or when the
    chain is exhausted. Callers retain the application's historical None-on-
    failure behavior in ``generate_video_subject``.
    """
    chain = list(providers if providers is not None else build_provider_chain())
    if not chain:
        raise RuntimeError("No LLM providers are configured")

    timeout = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "60"))
    last_error: Optional[Exception] = None
    for index, provider in enumerate(chain):
        try:
            client = client_factory(
                api_key=provider.api_key,
                base_url=provider.base_url,
                max_retries=0,
                timeout=timeout,
            )
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=provider.model,
            )
            content = response.choices[0].message.content
            if not content or not content.strip():
                raise RuntimeError("LLM provider returned empty content")
            return content.strip()
        except Exception as exc:
            last_error = exc
            has_fallback = index + 1 < len(chain)
            retryable = _is_retryable_provider_error(exc)
            status = _status_code(exc)
            status_label = status if status is not None else "transport"
            if retryable and has_fallback:
                next_provider = chain[index + 1]
                print(
                    f"LLM provider {provider.name}/{provider.model} failed "
                    f"(status={status_label}); trying "
                    f"{next_provider.name}/{next_provider.model}"
                )
                continue
            print(
                f"LLM provider {provider.name}/{provider.model} failed "
                f"(status={status_label}); no fallback attempted"
            )
            raise

    assert last_error is not None
    raise last_error


def generate_video_subject(api_key, prompt):
    """Compatibility wrapper used by ``video_manager``.

    ``api_key`` is retained for call-site compatibility; provider credentials
    are loaded independently so providers never share credentials.
    """
    del api_key
    try:
        return generate_with_provider_chain(prompt)
    except Exception:
        print("Failed to generate video subject (provider chain exhausted)")
        return None
