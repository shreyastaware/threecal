"""Conferencing provider registry."""

from app.domains.conferencing.models import ConferencingProviderName
from app.domains.conferencing.providers.base import ConferencingProvider
from app.domains.conferencing.providers.zoom import ZoomProvider


_PROVIDERS: dict[str, type[ConferencingProvider]] = {
    ConferencingProviderName.ZOOM.value: ZoomProvider,
}


def get_conferencing_provider(name: str) -> ConferencingProvider | None:
    provider_class = _PROVIDERS.get(name)
    return provider_class() if provider_class else None
