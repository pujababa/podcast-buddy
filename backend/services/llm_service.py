import os
import re
import json
import time
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from backend.config import GEMINI_API_KEY, GEMINI_MODEL, DEFAULT_GEMINI_MODEL

# Safe logger for Gemini service (never logs API keys or secrets)
logger = logging.getLogger("gemini_service")
if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [Gemini] %(message)s"))
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)


# =============================================================================
# Controlled Application Exceptions
# =============================================================================
class GeminiError(Exception):
    """Base exception for Gemini AI service errors."""
    pass


class GeminiConfigurationError(GeminiError):
    """Raised when the Gemini API key is missing or invalid in configuration."""
    pass


class GeminiAuthenticationError(GeminiError):
    """Raised when authentication with Gemini fails (e.g. invalid API key)."""
    pass


class GeminiRateLimitError(GeminiError):
    """Raised when Gemini quota or rate limit is reached."""
    pass


class GeminiTimeoutError(GeminiError):
    """Raised when the request to Gemini times out."""
    pass


class GeminiServiceError(GeminiError):
    """Raised when the Gemini service encounters a server/network error."""
    pass


class GeminiResponseError(GeminiError):
    """Raised when Gemini returns malformed, unparseable, or invalid JSON output."""
    pass


# =============================================================================
# Secret Redaction Helper
# =============================================================================
def redact_api_key(text: Any, api_key: Optional[str] = None) -> str:
    """Ensure no API key or sensitive token appears in error strings or logs."""
    if text is None:
        return ""
    clean = str(text)
    if api_key and str(api_key).strip():
        clean = clean.replace(str(api_key).strip(), "[REDACTED]")
    clean = re.sub(r'AIza[0-9A-Za-z-_]{35}', '[REDACTED_GEMINI_KEY]', clean)
    clean = re.sub(r'api_key=[^&\s"\']+', 'api_key=[REDACTED]', clean)
    return clean


# =============================================================================
# Prompt Construction
# =============================================================================
SYSTEM_INSTRUCTION = """You are an objective news intelligence assistant.
Your task is to analyze the provided news source summaries and synthesize verified, structured intelligence.

CRITICAL RULES:
1. GROUNDING: Base your analysis EXCLUSIVELY on the provided source information (title, publisher, snippet, date, and URL).
2. DO NOT INVENT: Do not fabricate facts, statistics, dates, quotes, or background context not present in the sources.
3. UNCERTAINTY: If the supplied sources are insufficient to establish a claim, or if publishers report conflicting details, state the uncertainty explicitly.
4. ATTRIBUTION: Preserve source attribution (e.g. "According to [Publisher]...").
5. MULTI-SOURCE ANALYSIS:
   - Identify common information corroborated across multiple sources.
   - Identify source-specific details mentioned by only one publisher.
   - Highlight conflicting or irreconcilable claims neutrally without taking a side.
6. TONE: Maintain a balanced, analytical, non-sensational, and neutral tone.
7. FORMAT: Return ONLY a valid JSON object matching the requested schema. No conversational preamble or trailing text."""


def build_news_analysis_prompt(sources: List[Dict[str, Any]]) -> str:
    """Build the prompt containing the source metadata for Gemini."""
    sources_text = []
    for idx, s in enumerate(sources, 1):
        source_id = s.get("article_id") or s.get("id") or f"src-{idx}"
        title = s.get("title") or "Untitled"
        publisher = s.get("publisher") or "Unknown Publisher"
        snippet = s.get("snippet") or "No preview snippet available."
        date = s.get("date") or "Date unspecified"
        url = s.get("url") or "URL not provided"

        sources_text.append(
            f"--- Source #{idx} [ID: {source_id}] ---\n"
            f"Publisher: {publisher}\n"
            f"Date: {date}\n"
            f"Title: {title}\n"
            f"Snippet: {snippet}\n"
            f"URL: {url}"
        )

    formatted_sources = "\n\n".join(sources_text)

    prompt = f"""Analyze the following {len(sources)} news source(s) and produce structured news intelligence.

SUPPLIED SOURCES:
{formatted_sources}

REQUIRED JSON SCHEMA:
{{
  "overview": "A concise executive summary synthesized strictly from the supplied sources.",
  "key_points": [
    "Key takeaway 1 supported by sources",
    "Key takeaway 2 supported by sources"
  ],
  "important_facts": [
    "Specific verifiable fact or metric mentioned in sources"
  ],
  "entities": [
    {{
      "name": "Entity Name",
      "type": "person|organization|place|technology|other",
      "context": "Context or role described in the sources"
    }}
  ],
  "topics": [
    "Topic or subject area 1",
    "Topic or subject area 2"
  ],
  "source_insights": [
    {{
      "source_id": "source id matching supplied source",
      "summary": "Brief summary of what this specific source reports",
      "key_claims": [
        "Primary claim made by this source"
      ]
    }}
  ],
  "confidence": "high|medium|low",
  "limitations": [
    "Explicit statement of limitations (e.g. analysis based on article snippets rather than full text, missing corroboration, etc.)"
  ]
}}

Return ONLY the raw JSON object conforming to the schema above."""
    return prompt


# =============================================================================
# JSON Parsing and Validation
# =============================================================================
def extract_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """
    Safely extract and parse JSON from model output, handling potential markdown code blocks.
    Raises GeminiResponseError if parsing fails.
    """
    if not raw_text or not str(raw_text).strip():
        raise GeminiResponseError("Gemini returned an empty response.")

    text = str(raw_text).strip()

    # Strip markdown code blocks if present (e.g. ```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Gemini response as JSON: %s", exc)
        raise GeminiResponseError(f"Malformed JSON returned by Gemini: {exc}") from exc

    if not isinstance(data, dict):
        raise GeminiResponseError("Expected top-level JSON object from Gemini, got " + type(data).__name__)

    return data


def validate_and_normalize_intelligence(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate required schema fields and normalize optional fields.
    Raises GeminiResponseError if required fields are missing or have invalid types.
    """
    # 1. Overview (required string)
    if "overview" not in data or not isinstance(data["overview"], str) or not data["overview"].strip():
        raise GeminiResponseError("Missing or invalid required field 'overview' in Gemini response.")
    overview = data["overview"].strip()

    # 2. Key Points (required list of strings)
    if "key_points" not in data or not isinstance(data["key_points"], list):
        raise GeminiResponseError("Missing or invalid required field 'key_points' (must be a list).")
    key_points = [str(p).strip() for p in data["key_points"] if str(p).strip()]

    # 3. Important Facts (required list of strings)
    if "important_facts" not in data or not isinstance(data["important_facts"], list):
        raise GeminiResponseError("Missing or invalid required field 'important_facts' (must be a list).")
    important_facts = [str(f).strip() for f in data["important_facts"] if str(f).strip()]

    # 4. Entities (list of entity dicts)
    raw_entities = data.get("entities")
    if not isinstance(raw_entities, list):
        raw_entities = []
    entities = []
    for item in raw_entities:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            ent_type = str(item.get("type") or "other").strip().lower()
            context = str(item.get("context") or "").strip()
            if name:
                entities.append({
                    "name": name,
                    "type": ent_type if ent_type in ("person", "organization", "place", "technology", "other") else "other",
                    "context": context
                })

    # 5. Topics (list of strings)
    raw_topics = data.get("topics")
    if not isinstance(raw_topics, list):
        raw_topics = []
    topics = [str(t).strip() for t in raw_topics if str(t).strip()]

    # 6. Source Insights (list of dicts)
    raw_insights = data.get("source_insights")
    if not isinstance(raw_insights, list):
        raw_insights = []
    source_insights = []
    for item in raw_insights:
        if isinstance(item, dict):
            src_id = str(item.get("source_id") or "").strip()
            summary = str(item.get("summary") or "").strip()
            raw_claims = item.get("key_claims")
            claims = [str(c).strip() for c in raw_claims if str(c).strip()] if isinstance(raw_claims, list) else []
            source_insights.append({
                "source_id": src_id,
                "summary": summary,
                "key_claims": claims
            })

    # 7. Confidence (string: high|medium|low)
    conf = str(data.get("confidence") or "medium").strip().lower()
    confidence = conf if conf in ("high", "medium", "low") else "medium"

    # 8. Limitations (list of strings)
    raw_limits = data.get("limitations")
    if not isinstance(raw_limits, list):
        raw_limits = []
    limitations = [str(l).strip() for l in raw_limits if str(l).strip()]
    if not limitations:
        limitations = ["Intelligence generated strictly from supplied source summaries."]

    return {
        "overview": overview,
        "key_points": key_points,
        "important_facts": important_facts,
        "entities": entities,
        "topics": topics,
        "source_insights": source_insights,
        "confidence": confidence,
        "limitations": limitations
    }


# =============================================================================
# Gemini Service Implementation
# =============================================================================
class GeminiService:
    """
    Service for generating structured news intelligence using the Google GenAI SDK.
    Encapsulates SDK interactions, prompt formatting, validation, and error translation.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key
        self.model = model or os.getenv("GEMINI_MODEL", GEMINI_MODEL or DEFAULT_GEMINI_MODEL)
        self._client = None

    def get_api_key(self) -> str:
        """Retrieve and validate the Gemini API key from instance or environment."""
        key = self._api_key or os.getenv("GEMINI_API_KEY")
        if not key or not str(key).strip():
            logger.info("Gemini API key not configured in environment or instance")
            raise GeminiConfigurationError(
                "GEMINI_API_KEY is not configured on the server. Please add your key to the .env file."
            )
        return str(key).strip().strip('"').strip("'")

    def _get_client(self):
        """Lazy-initialize or return the google.genai Client."""
        if self._client is None:
            api_key = self.get_api_key()
            try:
                from google import genai
                self._client = genai.Client(api_key=api_key)
            except Exception as exc:
                logger.error("Failed to initialize Google GenAI client: %s", exc)
        return self._client

    def reset_client(self):
        """Reset cached client instance (primarily used for test isolation)."""
        self._client = None

    def generate_structured_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Send a prompt to Gemini requesting structured JSON output and parse the result safely.
        Encapsulates client access, error mapping, and JSON extraction.
        """
        client = self._get_client()

        logger.info(
            "[BEFORE GEMINI REQUEST] Requesting structured JSON | model=%s | prompt_len=%d",
            self.model,
            len(prompt)
        )

        max_attempts = 3
        response = None
        for attempt in range(max_attempts):
            try:
                from google.genai import types

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=temperature
                )

                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config
                )

                logger.info("[AFTER GEMINI RESPONSE] Structured JSON response received from model=%s", self.model)
                break
            except Exception as exc:
                exc_msg = str(exc).lower()
                is_transient = any(term in exc_msg for term in ("503", "unavailable", "high demand", "overloaded", "spikes in demand"))
                if is_transient and attempt < max_attempts - 1:
                    backoff = (attempt + 1) * 3.0
                    logger.warning("[RETRY] Transient Gemini 503/high-demand error on attempt %d/%d. Waiting %.1fs before retry...", attempt + 1, max_attempts, backoff)
                    time.sleep(backoff)
                    continue
                self._handle_gemini_exception(exc)

        # Extract text from response
        raw_text = getattr(response, "text", None)
        if not raw_text:
            logger.error("Gemini response contained no text content.")
            raise GeminiResponseError("Gemini returned an empty response body.")

        logger.info("[BEFORE JSON PARSE] Deserializing Gemini response text...")
        raw_json = extract_and_parse_json(raw_text)
        logger.info("[AFTER JSON PARSE] Successfully parsed structured JSON.")
        return raw_json

    def generate_news_intelligence(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze selected news sources and generate verified, structured intelligence.

        :param sources: List of source dictionaries (must contain title, publisher, snippet, url).
        :return: Validated intelligence dictionary matching required schema.
        :raises GeminiConfigurationError: If API key is missing.
        :raises GeminiAuthenticationError: If API key is invalid/unauthorized.
        :raises GeminiRateLimitError: If rate limit/quota is exceeded.
        :raises GeminiTimeoutError: If the request times out.
        :raises GeminiResponseError: If response is malformed or invalid JSON.
        :raises GeminiServiceError: On other backend/network errors.
        """
        if not sources or not isinstance(sources, list):
            raise ValueError("At least one news source must be provided for intelligence generation.")

        prompt = build_news_analysis_prompt(sources)
        raw_json = self.generate_structured_json(
            prompt=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2
        )

        logger.info("[AFTER JSON PARSE] Validating structured intelligence schema...")
        intelligence = validate_and_normalize_intelligence(raw_json)
        logger.info("Successfully validated news intelligence with %d key points.", len(intelligence["key_points"]))

        return intelligence

    def _handle_gemini_exception(self, exc: Exception):
        """Map SDK errors to controlled application-level exceptions without leaking keys."""
        exc_str = redact_api_key(str(exc))
        exc_type = type(exc).__name__
        logger.warning("Gemini API call failed (%s): %s", exc_type, exc_str)

        # Check for google.genai errors or HTTP codes
        code = getattr(exc, "code", None)
        message = exc_str.lower()

        if code in (401, 403) or any(term in message for term in ("invalid api key", "unauthorized", "api_key_invalid", "permission_denied")):
            raise GeminiAuthenticationError("Authentication with Gemini failed. Please verify your GEMINI_API_KEY.") from None
        elif code in (429, 503) or any(term in message for term in ("resource_exhausted", "quota", "rate limit", "too many requests", "high demand", "spikes in demand")):
            raise GeminiRateLimitError("Gemini AI service is currently experiencing high demand. Please try again in a few moments.") from None
        elif any(term in message for term in ("deadline", "timeout", "timed out")):
            raise GeminiTimeoutError("The request to Gemini timed out. Please try again.") from None
        elif any(term in message for term in ("connection", "network", "unavailable", "dns")):
            raise GeminiServiceError("Unable to connect to the Gemini service. Please check network connectivity.") from None
        else:
            raise GeminiServiceError(f"Gemini service encountered an error: {exc_str}") from None


# Default singleton instance
gemini_service = GeminiService()
