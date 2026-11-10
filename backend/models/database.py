import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from backend.config import DATABASE_PATH

logger = logging.getLogger("podcast_buddy.database")
if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [DB] %(message)s"))
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)


class DatabaseError(Exception):
    """Custom exception for application database errors."""
    pass


def get_db_path(override_path: Optional[str] = None) -> str:
    """Return configured database path or override."""
    return override_path if override_path is not None else DATABASE_PATH


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Create and return a configured SQLite connection with foreign keys enabled
    and row factory set to sqlite3.Row.
    """
    path = get_db_path(db_path)
    parent_dir = os.path.dirname(os.path.abspath(path))
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Safely and idempotently initialize the database schema.
    Does not delete or alter existing data.
    Migration-safe: adds missing columns if existing table needs them.
    """
    path = get_db_path(db_path)
    logger.info("Initializing database at: %s", path)

    conn = get_db_connection(path)
    try:
        with conn:
            # 1. Episodes table (Phase 4, Phase 5, Phase 6 fields)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    ai_status TEXT NOT NULL DEFAULT 'not_started',
                    ai_intelligence TEXT,
                    ai_generated_at TEXT,
                    script_status TEXT NOT NULL DEFAULT 'not_started',
                    podcast_script TEXT,
                    script_generated_at TEXT,
                    audio_status TEXT NOT NULL DEFAULT 'not_started',
                    audio_language TEXT,
                    audio_path TEXT,
                    audio_generated_at TEXT,
                    audio_error TEXT
                );
            """)

            # 2. Episode sources table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episode_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id INTEGER NOT NULL,
                    article_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    publisher TEXT NOT NULL,
                    snippet TEXT,
                    date TEXT,
                    url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
                );
            """)

            # 3. Indices
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episode_sources_episode_id
                ON episode_sources(episode_id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_created_at
                ON episodes(created_at);
            """)

            # 4. Migration safety: check existing columns in episodes table and add missing ones
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(episodes);")
            existing_cols = {col["name"] for col in cursor.fetchall()}

            if "ai_status" not in existing_cols:
                logger.info("Migrating: Adding ai_status column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN ai_status TEXT NOT NULL DEFAULT 'not_started';")

            if "ai_intelligence" not in existing_cols:
                logger.info("Migrating: Adding ai_intelligence column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN ai_intelligence TEXT;")

            if "ai_generated_at" not in existing_cols:
                logger.info("Migrating: Adding ai_generated_at column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN ai_generated_at TEXT;")

            if "script_status" not in existing_cols:
                logger.info("Migrating: Adding script_status column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN script_status TEXT NOT NULL DEFAULT 'not_started';")

            if "podcast_script" not in existing_cols:
                logger.info("Migrating: Adding podcast_script column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN podcast_script TEXT;")

            if "script_generated_at" not in existing_cols:
                logger.info("Migrating: Adding script_generated_at column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN script_generated_at TEXT;")

            if "audio_status" not in existing_cols:
                logger.info("Migrating: Adding audio_status column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN audio_status TEXT NOT NULL DEFAULT 'not_started';")

            if "audio_language" not in existing_cols:
                logger.info("Migrating: Adding audio_language column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN audio_language TEXT;")

            if "audio_path" not in existing_cols:
                logger.info("Migrating: Adding audio_path column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN audio_path TEXT;")

            if "audio_generated_at" not in existing_cols:
                logger.info("Migrating: Adding audio_generated_at column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN audio_generated_at TEXT;")

            if "audio_error" not in existing_cols:
                logger.info("Migrating: Adding audio_error column to episodes table")
                conn.execute("ALTER TABLE episodes ADD COLUMN audio_error TEXT;")


        logger.info("Database schema initialized successfully.")
    except sqlite3.Error as e:
        logger.error("Failed to initialize database: %s", e)
        raise DatabaseError("Database initialization failed") from e
    finally:
        conn.close()


def create_episode(
    title: str,
    description: str,
    articles: List[Dict[str, Any]],
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Atomically create a new podcast episode and link its selected article sources.
    Uses parameterized queries and a strict transaction.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            # Insert episode
            cursor.execute(
                """
                INSERT INTO episodes (title, description, status, created_at, updated_at)
                VALUES (?, ?, 'draft', ?, ?)
                """,
                (title.strip(), description.strip() if description else "", now, now)
            )
            episode_id = cursor.lastrowid

            # Insert sources
            for art in articles:
                art_id = str(art.get("id") or art.get("article_id") or "").strip()
                art_title = str(art.get("title") or "").strip()
                art_publisher = str(art.get("publisher") or "Unknown Publisher").strip()
                art_snippet = str(art.get("snippet") or "").strip()
                art_date = str(art.get("date") or "").strip()
                art_url = str(art.get("url") or "").strip()

                cursor.execute(
                    """
                    INSERT INTO episode_sources (
                        episode_id, article_id, title, publisher, snippet, date, url, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        episode_id,
                        art_id,
                        art_title,
                        art_publisher,
                        art_snippet,
                        art_date,
                        art_url,
                        now
                    )
                )

        # Retrieve newly created episode inside connection
        return get_episode(episode_id, db_path=db_path)
    except sqlite3.Error as e:
        logger.error("Database transaction error creating episode: %s", e)
        raise DatabaseError("Failed to create episode in database") from e
    finally:
        conn.close()


def get_episode(episode_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve an episode by ID along with all associated article sources and AI intelligence.
    Returns None if not found.
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, status, created_at, updated_at,
                   ai_status, ai_intelligence, ai_generated_at,
                   script_status, podcast_script, script_generated_at,
                   audio_status, audio_language, audio_path, audio_generated_at, audio_error
            FROM episodes
            WHERE id = ?
            """,
            (episode_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        episode = dict(row)

        # Parse AI intelligence JSON safely
        raw_intel = episode.pop("ai_intelligence", None)
        if raw_intel:
            try:
                episode["intelligence"] = json.loads(raw_intel)
            except Exception:
                episode["intelligence"] = None
        else:
            episode["intelligence"] = None

        if "ai_status" not in episode or not episode["ai_status"]:
            episode["ai_status"] = "not_started"

        # Parse podcast script JSON safely
        raw_script = episode.pop("podcast_script", None)
        if raw_script:
            try:
                episode["podcast_script"] = json.loads(raw_script)
            except Exception:
                episode["podcast_script"] = None
        else:
            episode["podcast_script"] = None

        if "script_status" not in episode or not episode["script_status"]:
            episode["script_status"] = "not_started"

        if "audio_status" not in episode or not episode["audio_status"]:
            episode["audio_status"] = "not_started"
        episode.setdefault("audio_language", None)
        episode.setdefault("audio_path", None)
        episode.setdefault("audio_generated_at", None)
        episode.setdefault("audio_error", None)

        # Fetch associated sources
        cursor.execute(
            """
            SELECT id, episode_id, article_id, title, publisher, snippet, date, url, created_at
            FROM episode_sources
            WHERE episode_id = ?
            ORDER BY id ASC
            """,
            (episode_id,)
        )
        sources_rows = cursor.fetchall()
        episode["sources"] = [dict(s) for s in sources_rows]
        return episode
    except sqlite3.Error as e:
        logger.error("Database error retrieving episode %s: %s", episode_id, e)
        raise DatabaseError("Failed to retrieve episode from database") from e
    finally:
        conn.close()


def list_episodes(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all episodes ordered newest first (by created_at DESC, id DESC).
    Includes associated sources, parsed AI intelligence, podcast script, and audio info.
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, status, created_at, updated_at,
                   ai_status, ai_intelligence, ai_generated_at,
                   script_status, podcast_script, script_generated_at,
                   audio_status, audio_language, audio_path, audio_generated_at, audio_error
            FROM episodes
            ORDER BY created_at DESC, id DESC
            """
        )
        episode_rows = cursor.fetchall()
        episodes = []

        for row in episode_rows:
            ep = dict(row)
            raw_intel = ep.pop("ai_intelligence", None)
            if raw_intel:
                try:
                    ep["intelligence"] = json.loads(raw_intel)
                except Exception:
                    ep["intelligence"] = None
            else:
                ep["intelligence"] = None

            if "ai_status" not in ep or not ep["ai_status"]:
                ep["ai_status"] = "not_started"

            raw_script = ep.pop("podcast_script", None)
            if raw_script:
                try:
                    ep["podcast_script"] = json.loads(raw_script)
                except Exception:
                    ep["podcast_script"] = None
            else:
                ep["podcast_script"] = None

            if "script_status" not in ep or not ep["script_status"]:
                ep["script_status"] = "not_started"

            if "audio_status" not in ep or not ep["audio_status"]:
                ep["audio_status"] = "not_started"
            ep.setdefault("audio_language", None)
            ep.setdefault("audio_path", None)
            ep.setdefault("audio_generated_at", None)
            ep.setdefault("audio_error", None)


            cursor.execute(
                """
                SELECT id, episode_id, article_id, title, publisher, snippet, date, url, created_at
                FROM episode_sources
                WHERE episode_id = ?
                ORDER BY id ASC
                """,
                (ep["id"],)
            )
            ep["sources"] = [dict(s) for s in cursor.fetchall()]
            episodes.append(ep)

        return episodes
    except sqlite3.Error as e:
        logger.error("Database error listing episodes: %s", e)
        raise DatabaseError("Failed to list episodes from database") from e
    finally:
        conn.close()


def update_episode_ai_intelligence(
    episode_id: int,
    ai_status: str,
    intelligence: Optional[Dict[str, Any]] = None,
    generated_at: Optional[str] = None,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Atomically update AI intelligence and status for an episode.
    """
    now = datetime.now(timezone.utc).isoformat()
    raw_intelligence = json.dumps(intelligence) if intelligence is not None else None

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE episodes
                SET ai_status = ?,
                    ai_intelligence = ?,
                    ai_generated_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (ai_status, raw_intelligence, generated_at, now, episode_id)
            )
            if cursor.rowcount == 0:
                return None
        return get_episode(episode_id, db_path=db_path)
    except sqlite3.Error as e:
        logger.error("Database error updating AI intelligence for episode %s: %s", episode_id, e)
        raise DatabaseError("Failed to update AI intelligence in database") from e
    finally:
        conn.close()


def update_episode_podcast_script(
    episode_id: int,
    script_status: str,
    podcast_script: Optional[Dict[str, Any]] = None,
    generated_at: Optional[str] = None,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Atomically update podcast script and script status for an episode.
    """
    now = datetime.now(timezone.utc).isoformat()
    raw_script = json.dumps(podcast_script) if podcast_script is not None else None

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE episodes
                SET script_status = ?,
                    podcast_script = ?,
                    script_generated_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (script_status, raw_script, generated_at, now, episode_id)
            )
            if cursor.rowcount == 0:
                return None
        return get_episode(episode_id, db_path=db_path)
    except sqlite3.Error as e:
        logger.error("Database error updating podcast script for episode %s: %s", episode_id, e)
        raise DatabaseError("Failed to update podcast script in database") from e
    finally:
        conn.close()


def update_episode_audio(
    episode_id: int,
    audio_status: str,
    audio_language: Optional[str] = None,
    audio_path: Optional[str] = None,
    generated_at: Optional[str] = None,
    audio_error: Optional[str] = None,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Atomically update audio status, language, path, timestamp, and error for an episode.
    Preserves existing audio_path, audio_language, and generated_at if new values are not provided.
    """
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            # Fetch existing audio fields to avoid overwriting valid audio assets on retry/failure
            cursor.execute(
                "SELECT audio_language, audio_path, audio_generated_at FROM episodes WHERE id = ?",
                (episode_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            existing_lang, existing_path, existing_gen_at = row[0], row[1], row[2]
            final_lang = audio_language if audio_language is not None else existing_lang
            final_path = audio_path if audio_path is not None else existing_path
            final_gen_at = generated_at if generated_at is not None else existing_gen_at

            cursor.execute(
                """
                UPDATE episodes
                SET audio_status = ?,
                    audio_language = ?,
                    audio_path = ?,
                    audio_generated_at = ?,
                    audio_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (audio_status, final_lang, final_path, final_gen_at, audio_error, now, episode_id)
            )
            if cursor.rowcount == 0:
                return None
        return get_episode(episode_id, db_path=db_path)
    except sqlite3.Error as e:
        logger.error("Database error updating audio for episode %s: %s", episode_id, e)
        raise DatabaseError("Failed to update episode audio in database") from e
    finally:
        conn.close()


def delete_episode(episode_id: int, db_path: Optional[str] = None) -> bool:
    """
    Delete an episode and all associated sources.
    Returns True if episode was found and deleted, False if not found.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM episodes WHERE id = ?", (episode_id,))
            if not cursor.fetchone():
                return False

            # Explicitly delete sources as defense-in-depth alongside ON DELETE CASCADE
            cursor.execute("DELETE FROM episode_sources WHERE episode_id = ?", (episode_id,))
            cursor.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
            return True
    except sqlite3.Error as e:
        logger.error("Database error deleting episode %s: %s", episode_id, e)
        raise DatabaseError("Failed to delete episode from database") from e
    finally:
        conn.close()
