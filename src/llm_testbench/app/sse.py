"""Server-Sent Events, by hand: the format fits in three lines and it is better to know
it than to import it.

An SSE event is ``event: <name>\\ndata: <json>\\n\\n``. The client reads a
``text/event-stream`` stream and receives each block as soon as it is sent. Cancellation
comes from the client: when it closes the connection, the server stops iterating, which
closes the provider stream — and stops the billing of output tokens.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

from pydantic import BaseModel

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # nginx proxies must not buffer the stream
}


def encode(event: str, payload: BaseModel) -> bytes:
    return f"event: {event}\ndata: {payload.model_dump_json()}\n\n".encode()


async def until_disconnected[T: BaseModel](
    events: AsyncIterator[T],
    *,
    is_disconnected: Callable[[], Awaitable[bool]],
    kind: Callable[[T], str],
) -> AsyncIterator[bytes]:
    """Encode the events and stop as soon as the client has hung up."""
    async for event in events:
        if await is_disconnected():
            break
        yield encode(kind(event), event)
