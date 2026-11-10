import os
import re
import socket
import logging
import requests
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
DEFAULT_CONNECT_TIMEOUT = 5.0   # Explicit finite connection timeout (seconds)
DEFAULT_READ_TIMEOUT = 10.0     # Explicit finite read timeout (seconds)
DEFAULT_TIMEOUT = (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)

# Safe logger for SerpAPI service (never logs API keys or secrets)
logger = logging.getLogger("serpapi_service")
if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [SerpAPI] %(message)s"))
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)


class SerpAPIError(Exception):
    """Base exception for SerpAPI service errors."""
    pass


class SerpAPIConfigurationError(SerpAPIError):
    """Raised when the SerpAPI key is missing or not configured."""
    pass


class SerpAPIAuthError(SerpAPIError):
    """Raised when authentication with SerpAPI fails (e.g. invalid API key)."""
    pass


class SerpAPIRateLimitError(SerpAPIError):
    """Raised when SerpAPI quota or rate limit is reached."""
    pass


class SerpAPITimeoutError(SerpAPIError):
    """Raised when the request to SerpAPI times out."""
    pass


class SerpAPINetworkError(SerpAPIError):
    """Raised when network or connection issues occur."""
    pass


def redact_api_key(text: str, api_key: str = None) -> str:
    """Ensure no API key or sensitive token appears in error strings or logs."""
    if not text:
        return ""
    clean = str(text)
    if api_key and str(api_key).strip():
        clean = clean.replace(str(api_key).strip(), "[REDACTED]")
    clean = re.sub(r'api_key=[^&\s"\']+', 'api_key=[REDACTED]', clean)
    return clean


class SerpAPIService:
    """Service to handle news discovery via SerpAPI with error handling and result normalization."""

    def __init__(
        self,
        api_key: str = None,
        timeout=DEFAULT_TIMEOUT,
        connect_timeout: float = None,
        read_timeout: float = None
    ):
        self._api_key = api_key

        # Determine finite connect and read timeouts (seconds)
        try:
            conn_env = float(os.getenv("SERPAPI_CONNECT_TIMEOUT", DEFAULT_CONNECT_TIMEOUT))
            if conn_env <= 0:
                conn_env = DEFAULT_CONNECT_TIMEOUT
        except (ValueError, TypeError):
            conn_env = DEFAULT_CONNECT_TIMEOUT

        try:
            read_env = float(os.getenv("SERPAPI_READ_TIMEOUT", DEFAULT_READ_TIMEOUT))
            if read_env <= 0:
                read_env = DEFAULT_READ_TIMEOUT
        except (ValueError, TypeError):
            read_env = DEFAULT_READ_TIMEOUT

        conn = float(connect_timeout) if connect_timeout is not None else conn_env
        read = float(read_timeout) if read_timeout is not None else read_env

        if connect_timeout is not None or read_timeout is not None:
            self.timeout = (conn, read)
        elif isinstance(timeout, (tuple, list)) and len(timeout) == 2:
            self.timeout = (float(timeout[0]), float(timeout[1]))
        elif isinstance(timeout, (int, float)):
            self.timeout = (min(float(timeout), conn), float(timeout))
        else:
            self.timeout = (conn, read)

        # Enforce that self.timeout is always an explicit finite non-None tuple of positive floats
        if not isinstance(self.timeout, tuple) or len(self.timeout) != 2:
            self.timeout = DEFAULT_TIMEOUT
        elif self.timeout[0] <= 0 or self.timeout[1] <= 0:
            self.timeout = DEFAULT_TIMEOUT

    def get_api_key(self) -> str:
        """Retrieve and validate the SerpAPI key from instance or environment."""
        key = self._api_key or os.getenv("SERPAPI_API_KEY")
        if not key or not str(key).strip():
            logger.info("SerpAPI key not configured in environment or instance")
            raise SerpAPIConfigurationError(
                "SERPAPI_API_KEY is not configured on the server. Please add your key to the .env file."
            )
        return str(key).strip().strip('"').strip("'")

    def search_news(self, query: str, num_results: int = 10, timeout=None) -> list:
        """
        Search Google News via SerpAPI with explicit finite timeout, logging, and error handling.

        :param query: The search query string.
        :param num_results: Maximum number of articles to return.
        :param timeout: Optional override for request timeout.
        :return: List of normalized article dictionaries.
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")

        api_key = self.get_api_key()

        params = {
            "engine": "google_news",
            "q": query.strip(),
            "api_key": api_key,
            "gl": "us",
            "hl": "en"
        }

        # Resolve explicit finite timeout (strictly prevent timeout=None, <=0, or infinite wait)
        active_timeout = timeout if timeout is not None else self.timeout
        if isinstance(active_timeout, (tuple, list)) and len(active_timeout) == 2:
            try:
                conn_val = float(active_timeout[0])
                read_val = float(active_timeout[1])
                if conn_val > 0 and read_val > 0:
                    active_timeout = (conn_val, read_val)
                else:
                    active_timeout = DEFAULT_TIMEOUT
            except (ValueError, TypeError):
                active_timeout = DEFAULT_TIMEOUT
        elif isinstance(active_timeout, (int, float)) and active_timeout > 0:
            active_timeout = (min(float(active_timeout), DEFAULT_CONNECT_TIMEOUT), float(active_timeout))
        else:
            active_timeout = DEFAULT_TIMEOUT

        headers = {
            "User-Agent": "PodcastBuddy/1.0",
            "Accept": "application/json"
        }

        # Diagnostic log: BEFORE REQUEST
        logger.info(
            "[BEFORE REQUEST] Calling SerpAPI external endpoint: %s | query='%s' | timeout=%s",
            SERPAPI_ENDPOINT,
            redact_api_key(query, api_key),
            active_timeout
        )

        max_attempts = 2
        response = None
        for attempt in range(max_attempts):
            try:
                response = requests.get(
                    SERPAPI_ENDPOINT,
                    params=params,
                    headers=headers,
                    timeout=active_timeout
                )
                logger.info(
                    "[AFTER RESPONSE] HTTP response received: status_code=%s | reason=%s",
                    response.status_code,
                    response.reason
                )
                break
            except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout, requests.exceptions.Timeout, socket.timeout, TimeoutError) as exc:
                if attempt < max_attempts - 1:
                    logger.warning("SerpAPI request timed out (attempt %d/%d). Retrying once...", attempt + 1, max_attempts)
                    continue
                logger.warning("SerpAPI request timed out (timeout=%s): %s", active_timeout, type(exc).__name__)
                raise SerpAPITimeoutError("The news search request timed out. Please try again.") from None
            except (requests.exceptions.ConnectionError, socket.gaierror, socket.error, ConnectionRefusedError, ConnectionResetError) as exc:
                logger.warning("SerpAPI connection error: %s", type(exc).__name__)
                raise SerpAPINetworkError("Unable to connect to the news search service. Please check your connection.") from None
            except requests.exceptions.RequestException as exc:
                logger.warning("SerpAPI request exception: %s", type(exc).__name__)
                raise SerpAPINetworkError("Unable to connect to the news search service. Please check your connection.") from None
            except Exception as exc:
                logger.warning("SerpAPI unexpected request error: %s", type(exc).__name__)
                raise SerpAPINetworkError("Unable to connect to the news search service. Please check your connection.") from None

        # Handle specific HTTP status codes from SerpAPI
        if response.status_code in (401, 403):
            logger.warning("SerpAPI authentication failed with status %s", response.status_code)
            raise SerpAPIAuthError("Invalid SerpAPI key or unauthorized access.")
        elif response.status_code == 429:
            logger.warning("SerpAPI quota/rate limit exceeded with status 429")
            raise SerpAPIRateLimitError("SerpAPI search quota or rate limit exceeded.")
        elif response.status_code >= 500:
            logger.warning("SerpAPI server error with status %s", response.status_code)
            raise SerpAPIError("SerpAPI service is temporarily unavailable. Please try again later.")

        # Diagnostic log: BEFORE JSON PARSE
        logger.info("[BEFORE JSON PARSE] Parsing HTTP response body as JSON...")
        try:
            data = response.json()
            # Diagnostic log: AFTER JSON PARSE
            logger.info(
                "[AFTER JSON PARSE] JSON parsed successfully | top_level_keys=%s",
                list(data.keys()) if isinstance(data, dict) else type(data).__name__
            )
        except Exception as exc:
            logger.error("Failed to parse SerpAPI response as JSON: %s", type(exc).__name__)
            raise SerpAPIError("Invalid response format received from SerpAPI.") from None

        if not isinstance(data, dict):
            logger.error("Unexpected response structure from SerpAPI (expected dict, got %s)", type(data).__name__)
            raise SerpAPIError("Unexpected response structure received from SerpAPI.")

        # Check for error inside SerpAPI response body
        if "error" in data and data["error"]:
            err_msg = str(data["error"]).lower()
            safe_err = redact_api_key(str(data["error"]), api_key)
            logger.warning("SerpAPI returned error in response body: %s", safe_err)
            if any(term in err_msg for term in ("invalid api key", "unauthorized", "api_key", "forbidden", "your api key is not valid")):
                raise SerpAPIAuthError("Invalid SerpAPI key provided.")
            elif any(term in err_msg for term in ("quota", "rate limit", "run out of searches", "exceeded", "limit")):
                raise SerpAPIRateLimitError("SerpAPI search quota or rate limit exceeded.")
            elif any(term in err_msg for term in ("hasn't returned any results", "no results", "not match any")):
                return []
            else:
                raise SerpAPIError("News search provider returned an error.")

        if not response.ok:
            logger.warning("SerpAPI request returned non-OK status: %s", response.status_code)
            raise SerpAPIError(f"News search failed with status code {response.status_code}.")

        articles = self.normalize_results(data, limit=num_results)
        logger.info("Successfully normalized %d news articles from SerpAPI", len(articles))
        return articles

    def normalize_results(self, raw_data: dict, limit: int = 10) -> list:
        """
        Normalize raw SerpAPI Google News response into standardized dictionaries.

        Normalized structure:
        {
            "id": "news-1",
            "title": "...",
            "publisher": "...",
            "snippet": "...",
            "date": "...",
            "url": "..."
        }
        """
        if not isinstance(raw_data, dict):
            return []

        news_items = raw_data.get("news_results")
        if not isinstance(news_items, list):
            return []

        normalized = []
        counter = 1

        for item in news_items:
            if counter > limit:
                break

            parsed = self._normalize_single_item(item, counter)
            if parsed:
                normalized.append(parsed)
                counter += 1

            # Some SerpAPI Google News results group sub-stories inside a 'stories' array
            sub_stories = item.get("stories") if isinstance(item, dict) else None
            if isinstance(sub_stories, list):
                for sub in sub_stories:
                    if counter > limit:
                        break
                    parsed_sub = self._normalize_single_item(sub, counter)
                    if parsed_sub:
                        normalized.append(parsed_sub)
                        counter += 1

        return normalized

    def _normalize_single_item(self, item: dict, index: int) -> dict:
        """Safely normalize a single SerpAPI news item."""
        if not isinstance(item, dict):
            return None

        # URL - Must be non-empty string to represent a readable article
        url = str(item.get("link") or item.get("url") or "").strip()
        if not url:
            return None

        # Title
        raw_title = item.get("title")
        title = str(raw_title).strip() if raw_title is not None else ""
        if not title:
            title = "Untitled Article"

        # Publisher / Source
        source = item.get("source")
        if isinstance(source, dict):
            publisher = source.get("name") or source.get("title") or "Unknown Publisher"
        elif isinstance(source, str) and source.strip():
            publisher = source.strip()
        else:
            publisher = "Unknown Publisher"

        # Snippet
        raw_snippet = item.get("snippet")
        snippet = str(raw_snippet).strip() if raw_snippet is not None else ""

        # Date
        raw_date = item.get("date")
        date = str(raw_date).strip() if raw_date is not None else ""

        # ID
        item_id = f"news-{index}"

        return {
            "id": item_id,
            "title": title,
            "publisher": str(publisher).strip(),
            "snippet": snippet,
            "date": date,
            "url": str(url).strip()
        }


# Default singleton instance
serpapi_service = SerpAPIService()
