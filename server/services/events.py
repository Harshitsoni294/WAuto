import logging
from typing import Any

logger = logging.getLogger(__name__)

_sio = None

def set_sio(sio):
    global _sio
    _sio = sio
    logger.info("Socket.IO emitter configured in events module")

async def emit(event: str, data: Any):
    try:
        if _sio is not None:
            await _sio.emit(event, data)
    except Exception as e:
        logger.error(f"Failed to emit socket event '{event}': {e}")
