"""
Helper functions to handle images passed in messages
"""

import base64

from httpx import Response

import litellm
from litellm import verbose_logger
from litellm.caching.caching import InMemoryCache

MAX_IMGS_IN_MEMORY = 10

in_memory_cache = InMemoryCache(max_size_in_memory=MAX_IMGS_IN_MEMORY)


def _process_image_response(response: Response, url: str) -> str:
    # If the response status is not OK, do not raise immediately — return None
    # so callers can decide whether to retry or fail gracefully.
    if response.status_code != 200:
        verbose_logger.warning(
            f"Unable to fetch image from URL. Status code: {response.status_code}, url={url}"
        )
        return None

    image_bytes = response.content
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    image_type = response.headers.get("Content-Type")
    if image_type is None:
        img_type = url.split(".")[-1].lower()
        _img_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }.get(img_type)
        if _img_type is None:
            # Unsupported image format — log and return None to allow callers to handle.
            verbose_logger.warning(
                f"Unsupported image format for url={url}. Detected extension={img_type}."
            )
            return None
        img_type = _img_type
    else:
        img_type = image_type

    result = f"data:{img_type};base64,{base64_image}"
    in_memory_cache.set_cache(url, result)
    return result


async def async_convert_url_to_base64(url: str) -> str:
    cached_result = in_memory_cache.get_cache(url)
    if cached_result:
        return cached_result

    client = litellm.module_level_aclient
    for _ in range(3):
        try:
            response = await client.get(url, follow_redirects=True)
            return _process_image_response(response, url)
        except Exception:
            pass
    raise Exception(
        f"Error: Unable to fetch image from URL after 3 attempts. url={url}"
    )


def convert_url_to_base64(url: str) -> str:
    cached_result = in_memory_cache.get_cache(url)
    if cached_result:
        return cached_result

    client = litellm.module_level_client
    for _ in range(3):
        try:
            response = client.get(url, follow_redirects=True)
            result = _process_image_response(response, url)
            # If processing returned a valid base64 string, return it. If None, treat as retryable.
            if result:
                return result
            # Otherwise raise to trigger the retry logic in this loop.
            raise Exception(f"Non-OK response or unsupported image for url={url}, status={response.status_code}")
        except Exception as e:
            verbose_logger.exception(e)
            # continue to next attempt
            pass
    raise Exception(
        f"Error: Unable to fetch image from URL after 3 attempts. url={url}"
    )
