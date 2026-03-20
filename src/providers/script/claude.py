"""Claude-based script generation."""

from __future__ import annotations

import json

import anthropic

from src.pipeline.models import Script
from src.providers.base import ScriptProvider

SYSTEM_PROMPT = """You are a viral short-form video scriptwriter. You create scripts for
vertical videos (Reels/Shorts/TikTok) that are engaging, fast-paced, and designed to hook
viewers in the first 2 seconds.

Your scripts must:
1. Start with a powerful HOOK (first 2-3 seconds) — a question, bold claim, or surprising fact
2. Deliver VALUE in the body — keep it punchy, use short sentences
3. End with a natural CTA that plugs the product WITHOUT being salesy — make it feel like a genuine recommendation
4. Be written to sound natural when read aloud (conversational, not formal)

IMPORTANT: The product mention should feel NATIVE, not like an ad. Weave it into the story naturally.

Respond ONLY with valid JSON in this exact format:
{
    "hook": "The attention-grabbing opening line (2-3 seconds when spoken)",
    "body": "The main content, educational or entertaining (15-25 seconds when spoken)",
    "cta": "Natural call-to-action mentioning the product (3-5 seconds when spoken)",
    "title": "Short catchy title for the video (max 100 chars)",
    "description": "Video description with context (2-3 sentences)",
    "hashtags": ["relevant", "hashtags", "5to8"],
    "visual_keywords": ["keyword1", "keyword2", "keyword3"]
}"""


class ClaudeScriptProvider(ScriptProvider):
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

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

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        # Handle potential markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

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
