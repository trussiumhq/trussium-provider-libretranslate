import json

import httpx
import pytest
from trussium.capabilities.translation import (
    TranslationCapability,
    TranslationRequest,
    TranslationResponse,
)

from trussium_provider_libretranslate import (
    LibreTranslateProviderError,
    LibreTranslateTranslationCapability,
)


def make_request(
    *, source_language: str | None = "en", input_text: list[str] | None = None
) -> TranslationRequest:
    return TranslationRequest(
        model="nllb",
        input=input_text or ["Hello"],
        source_language=source_language,
        target_language="fr",
    )


@pytest.mark.anyio
async def test_translation_normalizes_response_and_detected_language() -> None:
    seen_payloads: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/translate"
        payload = json.loads(request.content)
        seen_payloads.append(payload)
        return httpx.Response(
            200,
            json={"translatedText": "Bonjour", "detectedLanguage": {"language": "en"}},
        )

    client = httpx.AsyncClient(
        base_url="http://testserver",
        transport=httpx.MockTransport(handler),
    )
    capability = LibreTranslateTranslationCapability(client=client)
    try:
        response = await capability.translate(make_request(source_language=None))
    finally:
        await client.aclose()

    assert isinstance(response, TranslationResponse)
    assert response.provider == "libretranslate"
    assert response.model == "nllb"
    assert len(response.translations) == 1
    assert response.translations[0].text == "Bonjour"
    assert response.translations[0].source_language == "en"
    assert response.translations[0].target_language == "fr"
    assert isinstance(capability, TranslationCapability)
    assert seen_payloads == [{"q": "Hello", "source": "auto", "target": "fr", "format": "text"}]


@pytest.mark.anyio
async def test_explicit_source_language_takes_precedence_over_detection() -> None:
    client = httpx.AsyncClient(
        base_url="http://testserver",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={"translatedText": "Bonjour", "detectedLanguage": {"language": "de"}},
            )
        ),
    )
    capability = LibreTranslateTranslationCapability(client=client)
    try:
        response = await capability.translate(make_request())
    finally:
        await client.aclose()

    assert response.translations[0].source_language == "en"


@pytest.mark.anyio
async def test_each_input_is_translated_in_order() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        text = json.loads(request.content)["q"]
        seen.append(text)
        return httpx.Response(200, json={"translatedText": f"{text}-fr"})

    client = httpx.AsyncClient(
        base_url="http://testserver",
        transport=httpx.MockTransport(handler),
    )
    capability = LibreTranslateTranslationCapability(client=client)
    try:
        response = await capability.translate(make_request(input_text=["one", "two"]))
    finally:
        await client.aclose()

    assert seen == ["one", "two"]
    assert [item.text for item in response.translations] == ["one-fr", "two-fr"]


@pytest.mark.anyio
async def test_api_key_is_sent_without_exposing_it_in_errors() -> None:
    api_key = "private-test-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["api_key"] == api_key
        return httpx.Response(503)

    client = httpx.AsyncClient(base_url="http://testserver", transport=httpx.MockTransport(handler))
    capability = LibreTranslateTranslationCapability(client=client, api_key=api_key)
    try:
        with pytest.raises(LibreTranslateProviderError) as error:
            await capability.translate(make_request())
    finally:
        await client.aclose()

    assert str(error.value) == "LibreTranslate rejected the request"
    assert api_key not in str(error.value)


@pytest.mark.anyio
async def test_http_failure_is_bounded() -> None:
    client = httpx.AsyncClient(
        base_url="http://testserver",
        transport=httpx.MockTransport(lambda _: httpx.Response(503)),
    )
    capability = LibreTranslateTranslationCapability(client=client)
    try:
        with pytest.raises(
            LibreTranslateProviderError, match="LibreTranslate rejected the request"
        ):
            await capability.translate(make_request())
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_timeout_has_bounded_provider_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive request detail")

    client = httpx.AsyncClient(base_url="http://testserver", transport=httpx.MockTransport(handler))
    capability = LibreTranslateTranslationCapability(client=client)
    try:
        with pytest.raises(
            LibreTranslateProviderError, match="LibreTranslate request timed out"
        ) as error:
            await capability.translate(make_request())
    finally:
        await client.aclose()

    assert "sensitive request detail" not in str(error.value)


@pytest.mark.anyio
async def test_connection_failure_has_bounded_provider_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private endpoint details")

    client = httpx.AsyncClient(base_url="http://testserver", transport=httpx.MockTransport(handler))
    capability = LibreTranslateTranslationCapability(client=client)
    try:
        with pytest.raises(
            LibreTranslateProviderError, match="LibreTranslate connection failed"
        ) as error:
            await capability.translate(make_request())
    finally:
        await client.aclose()

    assert "private endpoint details" not in str(error.value)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"translatedText": ""},
        {"translatedText": 42},
        [],
        {"translatedText": "Bonjour", "detectedLanguage": {"language": 7}},
    ],
)
async def test_malformed_provider_responses_are_bounded(payload: object) -> None:
    client = httpx.AsyncClient(
        base_url="http://testserver",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    capability = LibreTranslateTranslationCapability(client=client)
    try:
        if isinstance(payload, dict) and payload.get("translatedText") == "Bonjour":
            response = await capability.translate(make_request(source_language=None))
            assert response.translations[0].source_language is None
        else:
            with pytest.raises(
                LibreTranslateProviderError,
                match="LibreTranslate returned an invalid response",
            ):
                await capability.translate(make_request())
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_provider_does_not_close_injected_client() -> None:
    client = httpx.AsyncClient(
        base_url="http://testserver",
        transport=httpx.MockTransport(lambda _: httpx.Response(200)),
    )
    capability = LibreTranslateTranslationCapability(client=client)
    await capability.aclose()
    assert not client.is_closed
    await client.aclose()


@pytest.mark.anyio
async def test_provider_closes_owned_client() -> None:
    capability = LibreTranslateTranslationCapability()
    client = capability._client
    assert client.timeout.read == 10.0
    assert client.timeout.connect == 3.0
    await capability.aclose()
    assert client.is_closed
