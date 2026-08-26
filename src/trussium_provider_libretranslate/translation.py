"""LibreTranslate translation adapter."""

from typing import Any
from uuid import uuid4

import httpx
from trussium.capabilities.translation import (
    TranslationCapability,
    TranslationRequest,
    TranslationResponse,
    TranslationResult,
)


class LibreTranslateProviderError(Exception):
    """Raised when LibreTranslate cannot provide a normalized response."""


class LibreTranslateTranslationCapability(TranslationCapability):
    """Normalize LibreTranslate's ``/translate`` API into Trussium contracts."""

    provider_name = "libretranslate"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:5000",
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url.rstrip("/"))
        self._owns_client = client is None
        self._api_key = api_key

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        results: list[TranslationResult] = []
        for text in request.input:
            payload: dict[str, Any] = {
                "q": text,
                "source": request.source_language or "auto",
                "target": request.target_language,
                "format": request.format,
            }
            if self._api_key is not None:
                payload["api_key"] = self._api_key
            try:
                response = await self._client.post("/translate", json=payload)
                response.raise_for_status()
                body = response.json()
                translated = body.get("translatedText")
                if not isinstance(translated, str) or not translated:
                    raise ValueError("missing translatedText")
            except httpx.TimeoutException as error:
                raise LibreTranslateProviderError("LibreTranslate request timed out") from error
            except httpx.HTTPStatusError as error:
                raise LibreTranslateProviderError("LibreTranslate rejected the request") from error
            except (httpx.RequestError, ValueError, TypeError) as error:
                raise LibreTranslateProviderError(
                    "LibreTranslate returned an invalid response"
                ) from error
            results.append(
                TranslationResult(
                    text=translated,
                    source_language=request.source_language,
                    target_language=request.target_language,
                )
            )
        return TranslationResponse(
            id=f"translation-{uuid4().hex}",
            provider=self.provider_name,
            model=request.model,
            translations=results,
        )
