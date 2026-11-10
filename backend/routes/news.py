from flask import Blueprint, request, jsonify
from backend.services.serpapi_service import (
    serpapi_service,
    SerpAPIConfigurationError,
    SerpAPIAuthError,
    SerpAPIRateLimitError,
    SerpAPITimeoutError,
    SerpAPINetworkError,
    SerpAPIError
)

news_bp = Blueprint("news", __name__, url_prefix="/api/news")

MAX_QUERY_LENGTH = 200


@news_bp.route("/search", methods=["GET"])
def search_news():
    """
    Search for news articles via SerpAPI.
    Query parameter: ?q=<search_query>
    """
    # 1. Validation: Missing 'q' query parameter
    if "q" not in request.args:
        return jsonify({
            "success": False,
            "error": "Query parameter 'q' is required and cannot be empty.",
            "code": "MISSING_QUERY"
        }), 400

    raw_query = request.args.get("q", "")

    # 2. Validation: Empty 'q' query parameter
    if raw_query == "":
        return jsonify({
            "success": False,
            "error": "Query parameter 'q' is required and cannot be empty.",
            "code": "EMPTY_QUERY"
        }), 400

    clean_query = raw_query.strip()

    # 3. Validation: Whitespace-only 'q' query parameter
    if not clean_query:
        return jsonify({
            "success": False,
            "error": "Query parameter 'q' cannot be blank or whitespace only.",
            "code": "WHITESPACE_QUERY"
        }), 400

    # 4. Validation: Excessively long 'q' query parameter
    if len(clean_query) > MAX_QUERY_LENGTH:
        return jsonify({
            "success": False,
            "error": f"Query exceeds maximum allowed length of {MAX_QUERY_LENGTH} characters.",
            "code": "QUERY_TOO_LONG"
        }), 400

    try:
        articles = serpapi_service.search_news(query=clean_query)
        return jsonify({
            "success": True,
            "query": clean_query,
            "total_results": len(articles),
            "results": articles
        }), 200

    except SerpAPIConfigurationError:
        return jsonify({
            "success": False,
            "error": "News discovery service is not configured on the server. Please set SERPAPI_API_KEY in the server environment.",
            "code": "CONFIG_ERROR"
        }), 503

    except SerpAPIAuthError:
        return jsonify({
            "success": False,
            "error": "Authentication with the news search provider failed. Please verify the server API key.",
            "code": "AUTH_ERROR"
        }), 502

    except SerpAPIRateLimitError:
        return jsonify({
            "success": False,
            "error": "News discovery search quota or rate limit exceeded. Please try again later.",
            "code": "RATE_LIMIT_ERROR"
        }), 429

    except SerpAPITimeoutError:
        return jsonify({
            "success": False,
            "error": "The news discovery search timed out. Please try again.",
            "code": "TIMEOUT_ERROR"
        }), 504

    except SerpAPINetworkError:
        return jsonify({
            "success": False,
            "error": "Unable to reach the news search service. Please check network connectivity.",
            "code": "NETWORK_ERROR"
        }), 502

    except SerpAPIError:
        return jsonify({
            "success": False,
            "error": "News search service encountered an error.",
            "code": "PROVIDER_ERROR"
        }), 502

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "INVALID_QUERY"
        }), 400

    except Exception:
        # Avoid leaking internal stack trace or environment info
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred while processing the news search.",
            "code": "INTERNAL_ERROR"
        }), 500
