"""
Helper functions to handle images passed in messages
"""

import base64

from httpx import Response

import logging
import litellm

MAX_IMGS_IN_MEMORY = 10

in_memory_cache = None


def _get_in_memory_cache():
    global in_memory_cache
    if in_memory_cache is None:
        from litellm.caching.caching import InMemoryCache

        in_memory_cache = InMemoryCache(max_size_in_memory=MAX_IMGS_IN_MEMORY)
    return in_memory_cache


def _process_image_response(response: Response, url: str) -> str:
    if response.status_code != 200:
        # Raise so callers can handle retry / logging; include status for diagnostics
        raise Exception(
            f"Error: Unable to fetch image from URL. Status code: {response.status_code}, url={url}"
        )

    image_bytes = response.content
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    image_type = response.headers.get("Content-Type")
    if image_type is None:
        img_ext = url.split(".")[-1].lower()
        _img_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(img_ext)
        if _img_type is None:
            # Fallback to a generic binary content type instead of hard failing
            img_type = "application/octet-stream"
        else:
            img_type = _img_type
    else:
        img_type = image_type

    result = f"data:{img_type};base64,{base64_image}"
    _get_in_memory_cache().set_cache(url, result)
    return result


async def async_convert_url_to_base64(url: str) -> str:
    cached_result = _get_in_memory_cache().get_cache(url)
    if cached_result:
        return cached_result

    client = litellm.module_level_aclient
    logger = logging.getLogger(__name__)
    for _ in range(3):
        try:
            response = await client.get(url, follow_redirects=True)
            return _process_image_response(response, url)
        except Exception as e:
            # Log exceptions and continue retrying; protect against logging failures
            try:
                logger.exception("Failed to fetch/convert image (attempt). url=%s, error=%s", url, e)
            except Exception:
                pass
    raise Exception(
        f"Error: Unable to fetch image from URL after 3 attempts. url={url}"
    )


def convert_url_to_base64(url: str) -> str:
    cached_result = _get_in_memory_cache().get_cache(url)
    if cached_result:
        return cached_result

    client = litellm.module_level_client
    logger = logging.getLogger(__name__)
    for _ in range(3):
        try:
            response = client.get(url, follow_redirects=True)
            return _process_image_response(response, url)
        except Exception as e:
            # Use standard logging instead of verbose_logger to avoid import-time side effects
            try:
                logger.exception("Failed to fetch/convert image (attempt). url=%s, error=%s", url, e)
            except Exception:
                pass
    raise Exception(
        f"Error: Unable to fetch image from URL after 3 attempts. url={url}"
    )
