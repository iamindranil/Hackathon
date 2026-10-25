"""
Gemini LLM Client Wrapper
Integrates Google GenAI SDK (google-genai) with structured prompting,
temperature control, and fallback handling.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Explicitly load .env from the project root
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class GeminiClient:
    """
    Centralized client for Gemini model calls across Intake, Assessment, and Letter agents.
    """
    _client = None

    @classmethod
    def get_client(cls):
        if not GENAI_AVAILABLE:
            return None
        # Check both process env and .env file
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None
        if cls._client is None:
            try:
                cls._client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini client: {e}")
                return None
        return cls._client

    @classmethod
    def is_ai_live(cls) -> bool:
        """Returns True if a valid Gemini API key is configured."""
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        return bool(api_key and len(api_key.strip()) > 10)

    @classmethod
    def generate_content(
        cls,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: str = "gemini-3.5-flash-lite",
        temperature: float = 0.2,
        response_schema: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Executes a prompt against Gemini.
        Returns the text response or None if AI is offline.
        """
        client = cls.get_client()
        if not client:
            return None

        # Fallback list of models in case of temporary provider spike
        models_to_try = [model, "gemini-3.8-flash", "gemini-flash-latest"]

        for mod in models_to_try:
            try:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=system_instruction,
                )
                if response_schema:
                    config.response_mime_type = "application/json"
                    config.response_schema = response_schema

                response = client.models.generate_content(
                    model=mod,
                    contents=prompt,
                    config=config,
                )
                return response.text
            except Exception as e:
                print(f"Gemini API call to {mod} failed, trying next fallback: {e}")
                continue

        return None
