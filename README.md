# Trussium LibreTranslate provider

Standalone adapter for self-hosted [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate)
deployments. It implements Trussium's provider-neutral `TranslationCapability` and does not host or
manage LibreTranslate. The runtime and this adapter are installed independently.

## Install

Download the wheel from the project's GitHub Release and install it into the environment where the
Trussium runtime loads provider plugins. The LibreTranslate service itself is installed and operated
separately.

## Configure

```python
import os

from trussium_provider_libretranslate import LibreTranslateTranslationCapability

capability = LibreTranslateTranslationCapability(
    base_url="http://libretranslate:5000",
    api_key=os.environ["LIBRETRANSLATE_API_KEY"],  # omit if the instance requires no key
)
```

The adapter sends one asynchronous `POST /translate` request for each input string, preserves input
order, and returns the translated text with the requested target language. When source language is
`auto`, it uses LibreTranslate's detected-language response when available. Provider failures are
mapped to bounded timeout, connection, HTTP, or invalid-response errors; raw response bodies and
request details are not included in those errors.

The adapter-created HTTP client uses a 10-second total timeout and a 3-second connection timeout.
Call `await capability.aclose()` during application shutdown to close that client. If an
`httpx.AsyncClient` is injected, its lifetime remains the caller's responsibility and `aclose()` on
the capability will not close it. API keys are sent in the request body as required by LibreTranslate;
keep them in runtime secret configuration and never commit them to source control.

This project does not install, provision, or expose a LibreTranslate service. Apply the network,
TLS, authentication, and resource controls appropriate to your self-hosted deployment.
