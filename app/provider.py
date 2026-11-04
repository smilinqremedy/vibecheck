"""AI Provider client and network adapter for VibeCheck AI.

Handles HTTPS communication with OpenAI-compatible chat completion endpoints
using pure Python standard library (urllib.request). Enforces timeouts,
bounded exponential backoff for transient errors, and strict secret protection.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from app.config import Config


class ProviderError(Exception):
    """Base exception for provider communication failures."""


class ProviderAuthError(ProviderError):
    """Raised on 401/403 authorization failures."""


class ProviderRateLimitError(ProviderError):
    """Raised on 429 rate limit errors when retries are exhausted."""


class ProviderTimeoutError(ProviderError):
    """Raised when an HTTP request times out."""


class BaseProviderClient:
    """Abstract interface for AI model invocation."""

    def call_model(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        raise NotImplementedError


class HTTPProviderClient(BaseProviderClient):
    """Standard HTTPS provider client using urllib.request."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_seconds: int = 20,
        max_retries: int = 2,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.sleeper = sleeper
        self._validate_target_url()

    def _validate_target_url(self) -> None:
        """Validate URL scheme and hostname to prevent unintended network access."""
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in ("https", "http"):
            raise ProviderError(f"Unsupported URL scheme '{parsed.scheme}'. HTTPS required.")
        # Only permit unencrypted HTTP for localhost during local development/mock tests
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
            raise ProviderError("HTTP is only permitted for localhost/127.0.0.1; HTTPS required for remote providers.")
        if not parsed.netloc:
            raise ProviderError(f"Invalid host in base URL: '{self.base_url}'")

    @property
    def endpoint_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def call_model(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        """Execute HTTPS POST request to the provider with bounded retries on transient errors."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        encoded_data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "VibeCheck-AI/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        attempt = 0
        backoff_seconds = 0.5

        while True:
            attempt += 1
            req = urllib.request.Request(
                url=self.endpoint_url,
                data=encoded_data,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    resp_data = resp.read().decode("utf-8")
                    return self._extract_content(resp_data)

            except urllib.error.HTTPError as http_err:
                status = http_err.code
                err_body = ""
                try:
                    err_body = http_err.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

                # Sanitize error message: never leak secrets in logs
                masked_key = Config.redact_secret(self.api_key)

                if status in (401, 403):
                    raise ProviderAuthError(
                        f"Authentication failed (HTTP {status}). Check AI_API_KEY (Key masked: {masked_key}). Response: {err_body[:200]}"
                    ) from http_err

                # Transient errors: 429 (Rate Limit) and 5xx (Server Error)
                is_transient = status == 429 or (500 <= status < 600)
                if is_transient and attempt <= self.max_retries:
                    self.sleeper(backoff_seconds)
                    backoff_seconds *= 2.0
                    continue

                if status == 429:
                    raise ProviderRateLimitError(
                        f"Provider rate limit exceeded (HTTP 429) after {attempt} attempts. {err_body[:200]}"
                    ) from http_err

                raise ProviderError(
                    f"HTTP error {status} from provider: {err_body[:200]}"
                ) from http_err

            except (urllib.error.URLError, socket.timeout, TimeoutError) as net_err:
                # Distinguish timeout from generic network error
                reason = getattr(net_err, "reason", None)
                is_timeout = isinstance(net_err, (socket.timeout, TimeoutError)) or (
                    isinstance(reason, socket.timeout)
                )

                if attempt <= self.max_retries:
                    self.sleeper(backoff_seconds)
                    backoff_seconds *= 2.0
                    continue

                if is_timeout:
                    raise ProviderTimeoutError(
                        f"Provider request timed out after {self.timeout_seconds}s across {attempt} attempts."
                    ) from net_err

                raise ProviderError(f"Network error connecting to provider: {net_err}") from net_err

    def _extract_content(self, raw_json_str: str) -> str:
        """Parse chat completion envelope and extract message content string."""
        try:
            parsed = json.loads(raw_json_str)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Provider returned invalid JSON response: {exc}") from exc

        choices = parsed.get("choices")
        if not choices or not isinstance(choices, list):
            raise ProviderError(f"Provider response missing 'choices' list: {parsed}")

        message = choices[0].get("message", {})
        content = message.get("content")
        if content is None:
            raise ProviderError(f"Provider response choice missing message content: {choices[0]}")

        return str(content).strip()


class MockProviderClient(BaseProviderClient):
    """Deterministic offline provider client for unit tests and offline demos."""

    def __init__(
        self,
        canned_responses: Optional[Dict[str, str]] = None,
        default_response: Optional[str] = None,
        transient_failures_before_success: int = 0,
        fail_with_timeout: bool = False,
    ) -> None:
        self.canned_responses = canned_responses or {}
        self.default_response = default_response or "{}"
        self.transient_failures_remaining = transient_failures_before_success
        self.fail_with_timeout = fail_with_timeout
        self.call_history: List[List[Dict[str, str]]] = []
        self.call_count = 0

    def call_model(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        self.call_count += 1
        self.call_history.append(messages)

        if self.fail_with_timeout:
            raise ProviderTimeoutError("Simulated provider timeout.")

        if self.transient_failures_remaining > 0:
            self.transient_failures_remaining -= 1
            raise ProviderRateLimitError("Simulated 429 rate limit.")

        # Check if any message contains a review ID key in canned_responses
        combined_text = " ".join(m.get("content", "") for m in messages)
        for key, response_text in self.canned_responses.items():
            if key in combined_text:
                return response_text

        return self.default_response
