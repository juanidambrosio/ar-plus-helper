import asyncio
from telegram.error import NetworkError, RetryAfter

async def run_with_retry(async_func, retries=1, delay=1.0):
    for i in range(retries):
        try:
            return await async_func()
        except NetworkError as exc:
            if i == retries - 1:
                raise exc
            await asyncio.sleep(delay * (i + 1))
        except RetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
