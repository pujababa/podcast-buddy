import os
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any, Tuple
from flask import Blueprint, request, jsonify, send_file
from backend.config import AUDIO_OUTPUT_DIR
from backend.models.database import (
    create_episode,
    get_episode,
    list_episodes,
    delete_episode,
    update_episode_ai_intelligence,
    update_episode_podcast_script,
    update_episode_audio,
    DatabaseError
)
from backend.services.llm_service import (
    gemini_service,
    GeminiError,
    GeminiConfigurationError,
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiServiceError,
    GeminiResponseError
)
from backend.services.script_generator import (
    generate_podcast_script,
    ScriptGenerationError,
    ScriptValidationError
)
from backend.services.audio_processor import (
    AudioProcessingError,
    validate_safe_audio_path
)
from backend.services.tts_service import (
    tts_service,
    TTSError,
    TTSLanguageError,
    TTSSynthesisError,
    normalize_language,
    SUPPORTED_LANGUAGES
)

logger = logging.getLogger("podcast_buddy.routes.episodes")
episodes_bp = Blueprint("episodes", __name__, url_prefix="/api/episodes")


MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000
MAX_ARTICLES_PER_EPISODE = 50


def is_valid_http_url(url: Any) -> bool:
    """Validate that a URL string has an HTTP or HTTPS scheme and a non-empty network location."""
    if not isinstance(url, str):
        return False
    clean = url.strip()
    if not clean:
        return False
    try:
        parsed = urlparse(clean)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def validate_article(article: Any, index: int) -> Tuple[bool, str]:
    """
    Validate a single normalized article dictionary.
    Returns (is_valid, error_message).
    """
    if not isinstance(article, dict):
        return False, f"Article at index {index} must be a JSON object."

    # Article ID
    art_id = article.get("id") if "id" in article else article.get("article_id")
    if art_id is None or not isinstance(art_id, str) or not art_id.strip():
        return False, f"Article at index {index} is missing a required 'id'."
    if len(art_id.strip()) > 100:
        return False, f"Article 'id' at index {index} exceeds maximum allowed length of 100 characters."

    # Title
    title = article.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        return False, f"Article at index {index} is missing a required 'title'."
    if len(title.strip()) > 500:
        return False, f"Article 'title' at index {index} exceeds maximum allowed length of 500 characters."

    # Publisher
    publisher = article.get("publisher")
    if publisher is None or not isinstance(publisher, str) or not publisher.strip():
        return False, f"Article at index {index} is missing a required 'publisher'."
    if len(publisher.strip()) > 300:
        return False, f"Article 'publisher' at index {index} exceeds maximum allowed length of 300 characters."

    # Snippet (optional, must be string if present)
    snippet = article.get("snippet", "")
    if snippet is not None and not isinstance(snippet, str):
        return False, f"Article 'snippet' at index {index} must be a string."
    if snippet and len(snippet) > 5000:
        return False, f"Article 'snippet' at index {index} exceeds maximum allowed length of 5000 characters."

    # Date (optional, must be string if present)
    date = article.get("date", "")
    if date is not None and not isinstance(date, str):
        return False, f"Article 'date' at index {index} must be a string."
    if date and len(date) > 200:
        return False, f"Article 'date' at index {index} exceeds maximum allowed length of 200 characters."

    # URL (required, valid HTTP/HTTPS)
    url = article.get("url")
    if url is None or not is_valid_http_url(url):
        return False, f"Article at index {index} must contain a valid HTTP or HTTPS 'url'."
    if len(str(url).strip()) > 2048:
        return False, f"Article 'url' at index {index} exceeds maximum allowed length of 2048 characters."

    return True, ""


@episodes_bp.route("", methods=["POST"])
def handle_create_episode():
    """
    Create a new podcast episode and persist its selected news sources.
    POST /api/episodes
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request body must be valid JSON with 'Content-Type: application/json'.",
            "code": "INVALID_CONTENT_TYPE"
        }), 400

    try:
        body = request.get_json(silent=False)
    except Exception:
        return jsonify({
            "success": False,
            "error": "Malformed JSON payload.",
            "code": "MALFORMED_JSON"
        }), 400

    if not isinstance(body, dict):
        return jsonify({
            "success": False,
            "error": "Request payload must be a JSON object.",
            "code": "INVALID_PAYLOAD"
        }), 400

    # 1. Validate 'title'
    if "title" not in body:
        return jsonify({
            "success": False,
            "error": "Field 'title' is required.",
            "code": "MISSING_TITLE"
        }), 400

    raw_title = body.get("title")
    if not isinstance(raw_title, str) or not raw_title.strip():
        return jsonify({
            "success": False,
            "error": "Episode title cannot be empty or blank.",
            "code": "EMPTY_TITLE"
        }), 400

    clean_title = raw_title.strip()
    if len(clean_title) > MAX_TITLE_LENGTH:
        return jsonify({
            "success": False,
            "error": f"Episode title exceeds maximum allowed length of {MAX_TITLE_LENGTH} characters.",
            "code": "TITLE_TOO_LONG"
        }), 400

    # 2. Validate 'description'
    clean_description = ""
    if "description" in body and body["description"] is not None:
        raw_desc = body["description"]
        if not isinstance(raw_desc, str):
            return jsonify({
                "success": False,
                "error": "Episode description must be a string if provided.",
                "code": "INVALID_DESCRIPTION"
            }), 400
        clean_description = raw_desc.strip()
        if len(clean_description) > MAX_DESCRIPTION_LENGTH:
            return jsonify({
                "success": False,
                "error": f"Episode description exceeds maximum allowed length of {MAX_DESCRIPTION_LENGTH} characters.",
                "code": "DESCRIPTION_TOO_LONG"
            }), 400

    # 3. Validate 'articles'
    if "articles" not in body:
        return jsonify({
            "success": False,
            "error": "Field 'articles' is required.",
            "code": "MISSING_ARTICLES"
        }), 400

    articles = body.get("articles")
    if not isinstance(articles, list):
        return jsonify({
            "success": False,
            "error": "Field 'articles' must be an array of article objects.",
            "code": "INVALID_ARTICLES_TYPE"
        }), 400

    if len(articles) == 0:
        return jsonify({
            "success": False,
            "error": "At least one article must be selected to create an episode.",
            "code": "EMPTY_ARTICLES"
        }), 400

    if len(articles) > MAX_ARTICLES_PER_EPISODE:
        return jsonify({
            "success": False,
            "error": f"Maximum allowed articles per episode is {MAX_ARTICLES_PER_EPISODE}.",
            "code": "TOO_MANY_ARTICLES"
        }), 400

    # Validate each article object
    for idx, art in enumerate(articles):
        is_valid, err_msg = validate_article(art, idx)
        if not is_valid:
            return jsonify({
                "success": False,
                "error": err_msg,
                "code": "INVALID_ARTICLE",
                "article_index": idx
            }), 400

    # 4. Atomic Database Transaction
    try:
        episode = create_episode(
            title=clean_title,
            description=clean_description,
            articles=articles
        )
        return jsonify({
            "success": True,
            "episode": episode
        }), 201

    except DatabaseError as e:
        logger.error("Database error during episode creation: %s", e)
        return jsonify({
            "success": False,
            "error": "Unable to create podcast episode due to a server error. Please try again.",
            "code": "DATABASE_ERROR"
        }), 500
    except Exception as e:
        logger.error("Unexpected error creating episode: %s", e)
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred while creating the episode.",
            "code": "INTERNAL_ERROR"
        }), 500


def format_audio_duration(seconds: Optional[float]) -> Optional[str]:
    """Format duration in seconds into MM:SS or HH:MM:SS."""
    if seconds is None or seconds <= 0:
        return None
    total_secs = int(round(seconds))
    hrs = total_secs // 3600
    mins = (total_secs % 3600) // 60
    secs = total_secs % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def enrich_episode_computed_fields(ep: dict) -> dict:
    """
    Enrich an episode dictionary with accurate computed status flags,
    verified against actual data in SQLite and audio files on disk.
    Preserves all original database fields intact.
    """
    ep_id = ep.get("id")
    available_tracks = {}

    GENUINE_LANGUAGES = ("english", "hindi", "hinglish", "odia")

    if os.path.isdir(AUDIO_OUTPUT_DIR) and ep_id is not None:
        prefix = f"episode_{ep_id}_"
        try:
            for fn in os.listdir(AUDIO_OUTPUT_DIR):
                if fn.startswith(prefix) and (fn.lower().endswith(".mp3") or fn.lower().endswith(".wav")):
                    fp = os.path.join(AUDIO_OUTPUT_DIR, fn)
                    if os.path.isfile(fp) and os.path.getsize(fp) > 0:
                        parts = fn.split("_")
                        if len(parts) >= 3:
                            lang = parts[2].lower()
                            if lang in GENUINE_LANGUAGES:
                                if lang not in available_tracks or os.path.getmtime(fp) > os.path.getmtime(os.path.join(AUDIO_OUTPUT_DIR, available_tracks[lang])):
                                    available_tracks[lang] = fn
        except Exception as e:
            logger.warning("Error scanning audio directory for episode %s: %s", ep_id, e)

    # Also check if recorded audio_path is valid on disk
    recorded_path = ep.get("audio_path")
    if recorded_path and os.path.isdir(AUDIO_OUTPUT_DIR):
        rec_fp = os.path.join(AUDIO_OUTPUT_DIR, recorded_path)
        if os.path.isfile(rec_fp) and os.path.getsize(rec_fp) > 0:
            rec_parts = recorded_path.split("_")
            if len(rec_parts) >= 3 and rec_parts[2].lower() in GENUINE_LANGUAGES:
                rec_lang = rec_parts[2].lower()
            else:
                rec_lang = (ep.get("audio_language") or "").lower()
            if rec_lang in GENUINE_LANGUAGES and rec_lang not in available_tracks:
                available_tracks[rec_lang] = recorded_path

    has_audio = len(available_tracks) > 0
    ep["audio_tracks"] = available_tracks
    ep["available_audio_languages"] = list(available_tracks.keys())
    ep["audio_ready"] = has_audio

    # If audio_path is missing or invalid on disk, but tracks exist, choose default
    if (not recorded_path or not os.path.isfile(os.path.join(AUDIO_OUTPUT_DIR, recorded_path))) and has_audio:
        pref_lang = (ep.get("audio_language") or "english").lower()
        if pref_lang in available_tracks:
            ep["audio_path"] = available_tracks[pref_lang]
        else:
            first_lang = list(available_tracks.keys())[0]
            ep["audio_path"] = available_tracks[first_lang]
            if not ep.get("audio_language"):
                ep["audio_language"] = first_lang

    # Script readiness verification
    has_script = bool(ep.get("podcast_script") and isinstance(ep.get("podcast_script"), dict) and len(ep.get("podcast_script")) > 0)
    ep["script_ready"] = has_script

    # AI Intelligence readiness verification
    has_intel = bool(ep.get("intelligence") and isinstance(ep.get("intelligence"), dict) and len(ep.get("intelligence")) > 0)
    ep["ai_ready"] = has_intel

    # Audio duration calculation for primary track
    primary_duration = None
    target_audio_file = ep.get("audio_path")
    if target_audio_file and os.path.isdir(AUDIO_OUTPUT_DIR):
        target_fp = os.path.join(AUDIO_OUTPUT_DIR, target_audio_file)
        if os.path.isfile(target_fp) and os.path.getsize(target_fp) > 0:
            try:
                import miniaudio
                primary_duration = round(float(miniaudio.get_file_info(target_fp).duration), 2)
            except Exception:
                try:
                    from pydub.utils import mediainfo
                    info = mediainfo(target_fp)
                    d = float(info.get("duration", 0.0))
                    if d > 0:
                        primary_duration = round(d, 2)
                except Exception:
                    sz = os.path.getsize(target_fp)
                    if sz > 0:
                        primary_duration = round(sz / 16000.0, 2)

    ep["audio_duration_seconds"] = primary_duration
    ep["audio_duration_formatted"] = format_audio_duration(primary_duration)

    return ep


@episodes_bp.route("/<int:episode_id>", methods=["GET"])
def handle_get_episode(episode_id: int):
    """
    Retrieve an episode by ID with all associated source articles.
    GET /api/episodes/<episode_id>
    """
    try:
        episode = get_episode(episode_id)
        if not episode:
            return jsonify({
                "success": False,
                "error": f"Episode with ID {episode_id} not found.",
                "code": "NOT_FOUND"
            }), 404

        enrich_episode_computed_fields(episode)

        return jsonify({
            "success": True,
            "episode": episode
        }), 200

    except DatabaseError as e:
        logger.error("Database error retrieving episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "Unable to retrieve episode at this time.",
            "code": "DATABASE_ERROR"
        }), 500
    except Exception as e:
        logger.error("Unexpected error retrieving episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "An unexpected server error occurred.",
            "code": "INTERNAL_ERROR"
        }), 500


@episodes_bp.route("", methods=["GET"])
def handle_list_episodes():
    """
    List all stored episodes sorted newest first.
    GET /api/episodes
    """
    try:
        episodes = list_episodes()
        for ep in episodes:
            enrich_episode_computed_fields(ep)

        return jsonify({
            "success": True,
            "total": len(episodes),
            "episodes": episodes
        }), 200

    except DatabaseError as e:
        logger.error("Database error listing episodes: %s", e)
        return jsonify({
            "success": False,
            "error": "Unable to list episodes at this time.",
            "code": "DATABASE_ERROR"
        }), 500
    except Exception as e:
        logger.error("Unexpected error listing episodes: %s", e)
        return jsonify({
            "success": False,
            "error": "An unexpected server error occurred.",
            "code": "INTERNAL_ERROR"
        }), 500


@episodes_bp.route("/<int:episode_id>", methods=["DELETE"])
def handle_delete_episode(episode_id: int):
    """
    Delete an episode and its cascading article sources, plus safely clean up
    its associated generated audio files on disk. Never removes audio belonging
    to other episodes.
    DELETE /api/episodes/<episode_id>
    """
    try:
        # Check if episode exists
        episode = get_episode(episode_id)
        if not episode:
            return jsonify({
                "success": False,
                "error": f"Episode with ID {episode_id} not found.",
                "code": "NOT_FOUND"
            }), 404

        # Identify files strictly belonging to this episode (episode_{episode_id}_...)
        matched_audio_files = []
        if os.path.isdir(AUDIO_OUTPUT_DIR):
            prefix = f"episode_{episode_id}_"
            for fn in os.listdir(AUDIO_OUTPUT_DIR):
                if fn.startswith(prefix) and (fn.lower().endswith(".mp3") or fn.lower().endswith(".wav")):
                    parts = fn.split("_")
                    if len(parts) >= 3 and parts[0] == "episode" and parts[1] == str(episode_id):
                        matched_audio_files.append(fn)

        deleted = delete_episode(episode_id)
        if not deleted:
            return jsonify({
                "success": False,
                "error": f"Episode with ID {episode_id} not found.",
                "code": "NOT_FOUND"
            }), 404

        # Clean up associated audio files gracefully
        cleaned_files_count = 0
        for fn in matched_audio_files:
            try:
                full_path = validate_safe_audio_path(os.path.join(AUDIO_OUTPUT_DIR, fn), AUDIO_OUTPUT_DIR)
                if os.path.isfile(full_path):
                    os.remove(full_path)
                    cleaned_files_count += 1
                    logger.info("Cleaned up audio file for deleted episode %s: %s", episode_id, fn)
            except Exception as fe:
                logger.warning("Could not delete audio file %s for episode %s: %s", fn, episode_id, fe)

        return jsonify({
            "success": True,
            "message": f"Episode {episode_id} deleted successfully.",
            "audio_files_removed": cleaned_files_count
        }), 200

    except DatabaseError as e:
        logger.error("Database error deleting episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "Unable to delete episode at this time.",
            "code": "DATABASE_ERROR"
        }), 500
    except Exception as e:
        logger.error("Unexpected error deleting episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "An unexpected server error occurred.",
            "code": "INTERNAL_ERROR"
        }), 500


@episodes_bp.route("/<int:episode_id>/generate-intelligence", methods=["POST"])
def handle_generate_intelligence(episode_id: int):
    """
    Generate structured AI news intelligence for an episode's bundled sources.
    POST /api/episodes/<episode_id>/generate-intelligence
    """
    try:
        episode = get_episode(episode_id)
        if not episode:
            return jsonify({
                "success": False,
                "error": f"Episode with ID {episode_id} not found.",
                "code": "NOT_FOUND"
            }), 404

        sources = episode.get("sources", [])
        if not sources or len(sources) == 0:
            return jsonify({
                "success": False,
                "error": "Episode contains no source articles to analyze. Please select news stories first.",
                "code": "NO_SOURCES"
            }), 400

        # Mark status as processing in database
        update_episode_ai_intelligence(episode_id=episode_id, ai_status="processing")

        try:
            # Generate structured intelligence with Gemini
            intelligence = gemini_service.generate_news_intelligence(sources)
            now = datetime.now(timezone.utc).isoformat()

            # Store validated intelligence and mark completed
            update_episode_ai_intelligence(
                episode_id=episode_id,
                ai_status="completed",
                intelligence=intelligence,
                generated_at=now
            )

            return jsonify({
                "success": True,
                "episode_id": episode_id,
                "ai_status": "completed",
                "ai_generated_at": now,
                "intelligence": intelligence
            }), 200

        except GeminiConfigurationError as e:
            update_episode_ai_intelligence(episode_id=episode_id, ai_status="failed")
            return jsonify({
                "success": False,
                "error": "Gemini AI service is not configured on the server. Please set GEMINI_API_KEY in the server environment.",
                "code": "CONFIG_ERROR"
            }), 503

        except GeminiAuthenticationError as e:
            update_episode_ai_intelligence(episode_id=episode_id, ai_status="failed")
            return jsonify({
                "success": False,
                "error": "Authentication with Gemini AI failed. Please verify the server GEMINI_API_KEY.",
                "code": "AUTH_ERROR"
            }), 502

        except GeminiRateLimitError as e:
            update_episode_ai_intelligence(episode_id=episode_id, ai_status="failed")
            return jsonify({
                "success": False,
                "error": "Gemini AI rate limit or quota exceeded. Please try again later.",
                "code": "RATE_LIMIT_ERROR"
            }), 429

        except GeminiTimeoutError as e:
            update_episode_ai_intelligence(episode_id=episode_id, ai_status="failed")
            return jsonify({
                "success": False,
                "error": "The Gemini AI request timed out. Please try again.",
                "code": "TIMEOUT_ERROR"
            }), 504

        except GeminiResponseError as e:
            update_episode_ai_intelligence(episode_id=episode_id, ai_status="failed")
            return jsonify({
                "success": False,
                "error": "Gemini AI returned a malformed or invalid intelligence response.",
                "code": "RESPONSE_ERROR"
            }), 502

        except GeminiServiceError as e:
            update_episode_ai_intelligence(episode_id=episode_id, ai_status="failed")
            return jsonify({
                "success": False,
                "error": "Unable to communicate with the Gemini AI service. Please check network connectivity.",
                "code": "SERVICE_ERROR"
            }), 502

        except Exception as e:
            update_episode_ai_intelligence(episode_id=episode_id, ai_status="failed")
            logger.error("Unexpected error during intelligence generation: %s", e)
            return jsonify({
                "success": False,
                "error": "An unexpected error occurred while generating intelligence.",
                "code": "INTERNAL_ERROR"
            }), 500

    except DatabaseError as e:
        logger.error("Database error in generate_intelligence for episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "Database error while processing episode intelligence.",
            "code": "DATABASE_ERROR"
        }), 500
    except Exception as e:
        logger.error("Unexpected outer error in generate_intelligence: %s", e)
        return jsonify({
            "success": False,
            "error": "An unexpected server error occurred.",
            "code": "INTERNAL_ERROR"
        }), 500


@episodes_bp.route("/<int:episode_id>/generate-script", methods=["POST"])
def handle_generate_script(episode_id: int):
    """
    Generate a grounded, two-speaker podcast script from validated AI intelligence.
    POST /api/episodes/<episode_id>/generate-script
    """
    try:
        episode = get_episode(episode_id)
        if not episode:
            return jsonify({
                "success": False,
                "error": f"Episode with ID {episode_id} not found.",
                "code": "NOT_FOUND"
            }), 404

        intelligence = episode.get("intelligence")
        ai_status = episode.get("ai_status")
        if not intelligence or ai_status != "completed":
            return jsonify({
                "success": False,
                "error": "Generate AI intelligence before generating the podcast script.",
                "code": "INTELLIGENCE_REQUIRED"
            }), 400

        # Optional body parameter: length (default 'standard'), language (default 'english')
        length = "standard"
        language = "english"
        if request.is_json and request.json:
            req_length = request.json.get("length")
            if req_length and isinstance(req_length, str) and req_length.strip().lower() in ("short", "standard", "deep-dive"):
                length = req_length.strip().lower()
            req_lang = request.json.get("language") or request.json.get("script_language")
            if req_lang:
                try:
                    language = normalize_language(req_lang)
                except TTSLanguageError:
                    language = "english"

        # Mark status as processing in database
        update_episode_podcast_script(episode_id=episode_id, script_status="processing")

        try:
            # Generate grounded podcast script with language & script validation
            script = generate_podcast_script(
                episode=episode,
                intelligence=intelligence,
                length=length,
                language=language
            )
            now = datetime.now(timezone.utc).isoformat()

            # Save validated script and mark completed
            update_episode_podcast_script(
                episode_id=episode_id,
                script_status="completed",
                podcast_script=script,
                generated_at=now
            )
            return jsonify({
                "success": True,
                "episode_id": episode_id,
                "script_status": "completed",
                "script_language": language,
                "script_generated_at": now,
                "podcast_script": script
            }), 200

        except GeminiConfigurationError as e:
            update_episode_podcast_script(episode_id=episode_id, script_status="failed")
            return jsonify({
                "success": False,
                "error": "Gemini AI service is not configured on the server. Please set GEMINI_API_KEY in the server environment.",
                "code": "CONFIG_ERROR"
            }), 503

        except GeminiAuthenticationError as e:
            update_episode_podcast_script(episode_id=episode_id, script_status="failed")
            return jsonify({
                "success": False,
                "error": "Authentication with Gemini AI failed. Please verify the server GEMINI_API_KEY.",
                "code": "AUTH_ERROR"
            }), 502

        except GeminiRateLimitError as e:
            update_episode_podcast_script(episode_id=episode_id, script_status="failed")
            return jsonify({
                "success": False,
                "error": "Gemini AI rate limit or quota exceeded. Please try again later.",
                "code": "RATE_LIMIT_ERROR"
            }), 429

        except GeminiTimeoutError as e:
            update_episode_podcast_script(episode_id=episode_id, script_status="failed")
            return jsonify({
                "success": False,
                "error": "The Gemini AI request timed out. Please try again.",
                "code": "TIMEOUT_ERROR"
            }), 504

        except (ScriptValidationError, GeminiResponseError) as e:
            update_episode_podcast_script(episode_id=episode_id, script_status="failed")
            return jsonify({
                "success": False,
                "error": "Gemini AI returned a malformed or invalid podcast script response.",
                "code": "RESPONSE_ERROR"
            }), 502

        except (ScriptGenerationError, GeminiServiceError) as e:
            update_episode_podcast_script(episode_id=episode_id, script_status="failed")
            return jsonify({
                "success": False,
                "error": "Unable to communicate with the Gemini AI service. Please check network connectivity.",
                "code": "SERVICE_ERROR"
            }), 502

        except Exception as e:
            update_episode_podcast_script(episode_id=episode_id, script_status="failed")
            logger.error("Unexpected error during podcast script generation: %s", e)
            return jsonify({
                "success": False,
                "error": "An unexpected error occurred while generating the podcast script.",
                "code": "INTERNAL_ERROR"
            }), 500

    except DatabaseError as e:
        logger.error("Database error in generate_script for episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "Database error while processing episode script.",
            "code": "DATABASE_ERROR"
        }), 500
    except Exception as e:
        logger.error("Unexpected outer error in generate_script: %s", e)
        return jsonify({
            "success": False,
            "error": "An unexpected server error occurred.",
            "code": "INTERNAL_ERROR"
        }), 500


@episodes_bp.route("/<int:episode_id>/generate-audio", methods=["POST"])
def handle_generate_audio(episode_id: int):
    """
    Generate multi-speaker podcast audio from the Phase 6 podcast script.
    POST /api/episodes/<episode_id>/generate-audio
    """
    try:
        # 1. Check episode existence
        episode = get_episode(episode_id)
        if not episode:
            return jsonify({
                "success": False,
                "error": f"Episode with ID {episode_id} not found.",
                "code": "NOT_FOUND"
            }), 404

        # 2. Check script readiness
        script = episode.get("podcast_script")
        script_status = episode.get("script_status")
        if not script or script_status != "completed":
            return jsonify({
                "success": False,
                "error": "Generate a podcast script before generating audio.",
                "code": "SCRIPT_REQUIRED"
            }), 400

        # 3. Parse and validate language parameter
        target_language = "english"
        if request.is_json and request.json:
            req_lang = request.json.get("language") or request.json.get("audio_language")
            if req_lang:
                try:
                    target_language = normalize_language(req_lang)
                except TTSLanguageError as e:
                    return jsonify({
                        "success": False,
                        "error": str(e),
                        "code": "INVALID_LANGUAGE"
                    }), 400

        # 4. Atomically mark audio status as processing
        update_episode_audio(
            episode_id=episode_id,
            audio_status="processing",
            audio_language=target_language,
            audio_error=None
        )

        try:
            # 5. Synthesize and merge multi-speaker audio
            audio_result = tts_service.generate_podcast_audio(
                episode_id=episode_id,
                script=script,
                language=target_language
            )

            now_iso = audio_result.get("generated_at") or datetime.now(timezone.utc).isoformat()
            audio_path = audio_result["audio_path"]

            # 6. Persist completed state to database
            update_episode_audio(
                episode_id=episode_id,
                audio_status="completed",
                audio_language=target_language,
                audio_path=audio_path,
                generated_at=now_iso,
                audio_error=None
            )

            return jsonify({
                "success": True,
                "episode_id": episode_id,
                "audio_status": "completed",
                "audio_language": target_language,
                "audio_path": audio_path,
                "audio_url": f"/api/episodes/{episode_id}/audio",
                "audio_generated_at": now_iso,
                "duration_ms": audio_result.get("duration_ms", 0),
                "file_size": audio_result.get("file_size", 0),
                "format": audio_result.get("format", "wav")
            }), 200

        except TTSLanguageError as e:
            update_episode_audio(episode_id=episode_id, audio_status="failed", audio_error=str(e))
            return jsonify({
                "success": False,
                "error": str(e),
                "code": "INVALID_LANGUAGE"
            }), 400

        except TTSSynthesisError as e:
            update_episode_audio(episode_id=episode_id, audio_status="failed", audio_error=str(e))
            logger.error("TTS synthesis error for episode %s: %s", episode_id, e)
            return jsonify({
                "success": False,
                "error": f"Audio speech synthesis failed: {e}",
                "code": "TTS_ERROR"
            }), 502

        except AudioProcessingError as e:
            update_episode_audio(episode_id=episode_id, audio_status="failed", audio_error=str(e))
            logger.error("Audio processing error for episode %s: %s", episode_id, e)
            return jsonify({
                "success": False,
                "error": f"Audio processing failed: {e}",
                "code": "AUDIO_PROCESSING_ERROR"
            }), 500

        except TTSError as e:
            update_episode_audio(episode_id=episode_id, audio_status="failed", audio_error=str(e))
            logger.error("TTS error for episode %s: %s", episode_id, e)
            return jsonify({
                "success": False,
                "error": f"Audio generation error: {e}",
                "code": "TTS_ERROR"
            }), 502

        except Exception as e:
            update_episode_audio(episode_id=episode_id, audio_status="failed", audio_error=str(e))
            logger.error("Unexpected error during audio generation for episode %s: %s", episode_id, e)
            return jsonify({
                "success": False,
                "error": "An unexpected error occurred while generating podcast audio.",
                "code": "INTERNAL_ERROR"
            }), 500

    except DatabaseError as e:
        logger.error("Database error in generate_audio for episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "Database error while processing episode audio.",
            "code": "DATABASE_ERROR"
        }), 500
    except Exception as e:
        logger.error("Unexpected outer error in generate_audio for episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "An unexpected server error occurred.",
            "code": "INTERNAL_ERROR"
        }), 500


@episodes_bp.route("/<int:episode_id>/audio", methods=["GET"])
def handle_get_audio(episode_id: int):
    """
    Safely retrieve/stream the generated podcast audio file.
    Supports optional ?lang= or ?language= query parameter to stream specific language tracks.
    GET /api/episodes/<episode_id>/audio[?lang=<language>]
    """
    try:
        episode = get_episode(episode_id)
        if not episode:
            return jsonify({
                "success": False,
                "error": f"Episode with ID {episode_id} not found.",
                "code": "NOT_FOUND"
            }), 404

        requested_lang = (request.args.get("lang") or request.args.get("language") or "").strip().lower()
        selected_file = None

        if requested_lang:
            prefix = f"episode_{episode_id}_{requested_lang}_"
            if os.path.isdir(AUDIO_OUTPUT_DIR):
                candidates = [
                    f for f in os.listdir(AUDIO_OUTPUT_DIR)
                    if f.startswith(prefix) and (f.lower().endswith(".mp3") or f.lower().endswith(".wav"))
                ]
                if candidates:
                    candidates.sort(
                        key=lambda fn: os.path.getmtime(os.path.join(AUDIO_OUTPUT_DIR, fn)),
                        reverse=True
                    )
                    selected_file = candidates[0]

            # If no prefixed candidate was found, check if the episode's primary audio_path actually matches requested_lang
            if not selected_file and (episode.get("audio_language") or "").strip().lower() == requested_lang:
                cand_path = episode.get("audio_path")
                if cand_path:
                    parts = cand_path.split("_")
                    if len(parts) >= 3:
                        if parts[2].lower() == requested_lang:
                            selected_file = cand_path
                    else:
                        selected_file = cand_path

            # If a specific language was explicitly requested but neither prefix nor primary matches, return 404
            if not selected_file:
                return jsonify({
                    "success": False,
                    "error": f"Audio for language '{requested_lang}' has not been generated for this episode.",
                    "code": "LANGUAGE_TRACK_NOT_FOUND"
                }), 404
        else:
            selected_file = episode.get("audio_path")
            if not selected_file or not os.path.isfile(os.path.join(AUDIO_OUTPUT_DIR, selected_file)):
                if os.path.isdir(AUDIO_OUTPUT_DIR):
                    candidates = [
                        f for f in os.listdir(AUDIO_OUTPUT_DIR)
                        if f.startswith(f"episode_{episode_id}_") and (f.lower().endswith(".mp3") or f.lower().endswith(".wav"))
                    ]
                    if candidates:
                        candidates.sort(
                            key=lambda fn: os.path.getmtime(os.path.join(AUDIO_OUTPUT_DIR, fn)),
                            reverse=True
                        )
                        selected_file = candidates[0]

        if not selected_file:
            return jsonify({
                "success": False,
                "error": "Podcast audio has not been generated for this episode.",
                "code": "AUDIO_NOT_FOUND"
            }), 404

        # Validate security and confinement to AUDIO_OUTPUT_DIR
        target_abs_path = os.path.abspath(os.path.join(AUDIO_OUTPUT_DIR, selected_file))
        try:
            safe_abs_path = validate_safe_audio_path(target_abs_path, AUDIO_OUTPUT_DIR)
        except Exception:
            return jsonify({
                "success": False,
                "error": "Access to requested audio file is forbidden.",
                "code": "FORBIDDEN"
            }), 403

        if not os.path.isfile(safe_abs_path) or os.path.getsize(safe_abs_path) == 0:
            return jsonify({
                "success": False,
                "error": "Audio file not found on disk or is empty.",
                "code": "FILE_NOT_FOUND"
            }), 404

        mimetype = "audio/wav" if safe_abs_path.lower().endswith(".wav") else "audio/mpeg"
        download_flag = request.args.get("download", "").lower() in ("true", "1", "yes")
        if download_flag:
            raw_title = episode.get("title") or "podcast"
            safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in raw_title)[:30].strip("_")
            dl_filename = f"podcast_buddy_ep{episode_id}_{requested_lang or 'audio'}_{safe_title}.mp3"
            return send_file(safe_abs_path, mimetype=mimetype, as_attachment=True, download_name=dl_filename)

        return send_file(safe_abs_path, mimetype=mimetype, as_attachment=False)

    except Exception as e:
        logger.error("Error retrieving audio for episode %s: %s", episode_id, e)
        return jsonify({
            "success": False,
            "error": "Failed to retrieve podcast audio file.",
            "code": "INTERNAL_ERROR"
        }), 500

