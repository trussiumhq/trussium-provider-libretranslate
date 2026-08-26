# Trussium LibreTranslate provider

Standalone adapter for self-hosted [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate)
deployments. It implements Trussium's provider-neutral `TranslationCapability` and does not host or
manage LibreTranslate.

```python
from trussium_provider_libretranslate import LibreTranslateTranslationCapability

capability = LibreTranslateTranslationCapability(base_url="http://libretranslate:5000")
```

The adapter uses deterministic async HTTP calls, supports optional API keys, and never logs source or
translated text.
