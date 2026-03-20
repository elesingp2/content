"""OpenAI-based script generation."""

from __future__ import annotations

import json

import openai

from src.pipeline.models import Script
from src.providers.base import ScriptProvider
from src.providers.script.claude import SYSTEM_PROMPT


class OpenAIScriptProvider(ScriptProvider):
    def __init__(self, api_key: str):
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate_script(
        self,
        idea: str,
        product_name: str,
        product_tagline: str,
        product_description: str,
        product_cta: str,
        style: str = "engaging",
        tone: str = "confident",
        duration_seconds: int = 30,
        language: str = "en",
    ) -> Script:
        user_prompt = f"""Create a {duration_seconds}-second vertical video script about:
"{idea}"

Style: {style} | Tone: {tone} | Language: {language}

Product to naturally plug:
- Name: {product_name}
- Tagline: {product_tagline}
- What it does: {product_description}
- CTA: {product_cta}

Remember: the product mention should feel like a natural recommendation, not an ad."""

        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content.strip()
        data = json.loads(text)

        full_text = f"{data['hook']} {data['body']} {data['cta']}"

        return Script(
            hook=data["hook"],
            body=data["body"],
            cta=data["cta"],
            full_text=full_text,
            hashtags=data.get("hashtags", []),
            title=data.get("title", idea[:100]),
            description=data.get("description", ""),
        )
