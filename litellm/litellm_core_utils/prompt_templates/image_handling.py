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
    try:
        status = getattr(response, "status_code", None)
        if status != 200:
            # Treat non-200 responses as a transient failure so callers can retry.
            try:
                verbose_logger.debug("Non-200 response fetching image: status=%s, url=%s", status, url)
            except Exception:
                pass
            return None

        image_bytes = getattr(response, "content", None)
        if not image_bytes:
            try:
                verbose_logger.debug("No content in image response for url=%s", url)
            except Exception:
                pass
            return None

        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        image_type = None
        headers = getattr(response, "headers", None)
        if headers:
            image_type = headers.get("Content-Type")

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
                # Unsupported format; allow callers to handle/retry instead of raising here.
                try:
                    verbose_logger.debug(
                        "Unsupported image format for url=%s format=%s",
                        url,
                        img_type,
                    )
                except Exception:
                    pass
                return None
            img_type = _img_type
        else:
            img_type = image_type

        result = f"data:{img_type};base64,{base64_image}"
        try:
            in_memory_cache.set_cache(url, result)
        except Exception:
            # Cache failures should not break the flow.
            pass
        return result
    except Exception as e:
        # Protect callers from unexpected errors in processing and surface a None so callers can retry.
        try:
            verbose_logger.debug("Error processing image response for %s: %s", url, e, exc_info=True)
        except Exception:
            pass
        return None


async def async_convert_url_to_base64(url: str) -> str:
    cached_result = in_memory_cache.get_cache(url)
    if cached_result:
        return cached_result

    client = litellm.module_level_aclient
    for _ in range(3):
        try:
            response = await client.get(url, follow_redirects=True)
            result = _process_image_response(response, url)
            if result:
                return result
        except Exception as e:
            # Log the failure but never let logging errors mask the original problem
            try:
                verbose_logger.error("Failed to fetch image (async) %s: %s", url, e, exc_info=True)
            except Exception:
                pass
    raise Exception(f"Error: Unable to fetch image from URL after 3 attempts. url={url}")


def convert_url_to_base64(url: str) -> str:
    cached_result = in_memory_cache.get_cache(url)
    if cached_result:
        return cached_result

    client = litellm.module_level_client
    for _ in range(3):
        try:
            response = client.get(url, follow_redirects=True)
            # Support async clients that may return a coroutine from get()
            try:
                import inspect
                import asyncio

                if inspect.isawaitable(response):
                    try:
                        response = asyncio.run(response)
                    except Exception as e:
                        try:
                            verbose_logger.error(
                                "Failed to run async client.get synchronously for %s: %s",
                                url,
                                e,
                                exc_info=True,
                            )
                        except Exception:
                            pass
                        continue
            except Exception:
                # If introspection or running the coroutine fails, continue to retry.
                pass

            result = _process_image_response(response, url)
            if result:
                return result
        except Exception as e:
            # Avoid calling logger.exception directly (can raise in some environments).
            try:
                verbose_logger.error("Failed to fetch image %s: %s", url, e, exc_info=True)
            except Exception:
                pass
            # continue to next retry
            continue
    raise Exception(f"Error: Unable to fetch image from URL after 3 attempts. url={url}")
