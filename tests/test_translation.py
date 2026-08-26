import json

import httpx
import pytest
from trussium.capabilities.translation import TranslationRequest
from trussium_provider_libretranslate import LibreTranslateTranslationCapability


@pytest.mark.anyio
async def test_translation_normalizes_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/translate"
        assert json.loads(request.content) == {
            "q": "Hello",
            "source": "en",
            "target": "fr",
            "format": "text",
        }
        return httpx.Response(200, json={"translatedText": "Bonjour"})

    capability = LibreTranslateTranslationCapability(
        client=httpx.AsyncClient(
            base_url="http://testserver",
            transport=httpx.MockTransport(handler),
        )
    )
    response = await capability.translate(
        TranslationRequest(
            model="nllb", input=["Hello"], source_language="en", target_language="fr"
        )
    )
    assert response.provider == "libretranslate"
    assert response.translations[0].text == "Bonjour"


@pytest.mark.anyio
async def test_http_failure_is_bounded() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    capability = LibreTranslateTranslationCapability(client=client)
    with pytest.raises(Exception, match="invalid response"):
        await capability.translate(
            TranslationRequest(model="nllb", input=["Hello"], target_language="fr")
        )
