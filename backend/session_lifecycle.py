import asyncio


async def wait_for_conversation(client_task, gemini_task, timekeeper_task=None):
    """Only a conversation transport ending may close the session."""
    transports = (client_task, gemini_task)
    try:
        await asyncio.wait(transports, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (*transports, timekeeper_task):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (*transports, timekeeper_task) if task is not None),
            return_exceptions=True,
        )
