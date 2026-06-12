from openai import AsyncOpenAI

from .prompts import SYSTEM_PROMPT


async def complete(client: AsyncOpenAI, model: str, user_text: str) -> str:
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    return resp.choices[0].message.content or ""
