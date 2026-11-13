from openai import AsyncOpenAI
from . import config

_client = None


def client():
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.API_KEY, base_url=config.BASE_URL)
    return _client


async def stream(messages, tools=None, temperature=None, model=None):
    kw = dict(
        model=model or config.MODEL,
        messages=messages,
        temperature=config.TEMPERATURE if temperature is None else temperature,
        stream=True,
    )
    if tools:
        kw["tools"] = tools
        kw["tool_choice"] = "auto"
    s = await client().chat.completions.create(**kw)
    async for chunk in s:
        yield chunk