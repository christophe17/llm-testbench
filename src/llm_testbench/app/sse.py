"""Server-Sent Events, à la main : le format tient en trois lignes et il vaut mieux le
connaître que l'importer.

Un événement SSE est ``event: <nom>\\ndata: <json>\\n\\n``. Le client lit un flux
``text/event-stream`` et reçoit chaque bloc dès qu'il est envoyé. L'annulation vient du
client : quand il ferme la connexion, le serveur cesse d'itérer, ce qui ferme le flux du
provider — et arrête la facturation des tokens de sortie.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

from pydantic import BaseModel

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # les proxys nginx ne doivent pas tamponner le flux
}


def encode(event: str, payload: BaseModel) -> bytes:
    return f"event: {event}\ndata: {payload.model_dump_json()}\n\n".encode()


async def until_disconnected[T: BaseModel](
    events: AsyncIterator[T],
    *,
    is_disconnected: Callable[[], Awaitable[bool]],
    kind: Callable[[T], str],
) -> AsyncIterator[bytes]:
    """Encode les événements et s'arrête dès que le client a raccroché."""
    async for event in events:
        if await is_disconnected():
            break
        yield encode(kind(event), event)
