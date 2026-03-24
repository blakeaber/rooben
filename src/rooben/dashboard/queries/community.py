"""Community publishing CRUD queries."""

from __future__ import annotations

import json
import uuid

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]


def _decode_row(
    row: asyncpg.Record,
    json_fields: tuple[str, ...] = ("tags", "bundle_manifest"),
) -> dict:
    """Convert a DB row to a dict, decoding JSON string fields."""
    d = dict(row)
    for f in json_fields:
        val = d.get(f)
        if isinstance(val, str):
            try:
                d[f] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return d


# ── Create ────────────────────────────────────────────────────────────────


async def create_publication(pool: asyncpg.Pool, data: dict) -> dict:
    """Create a new community publication."""
    tags = data.get("tags", [])
    if isinstance(tags, list):
        tags = json.dumps(tags)

    bundle_manifest = data.get("bundle_manifest")
    if isinstance(bundle_manifest, (dict, list)):
        bundle_manifest = json.dumps(bundle_manifest)

    row = await pool.fetchrow(
        """INSERT INTO community_publications
           (id, artifact_type, artifact_id, author_id, author_name,
            status, published_at, title, description, tags, category,
            version, automated_checks_passed, review_notes,
            bundle_id, source_url, forked_from, bundle_manifest)
           VALUES ($1, $2, $3, $4, $5,
                   $6, $7, $8, $9, $10::jsonb, $11,
                   $12, $13, $14,
                   $15, $16, $17, $18)
           RETURNING *""",
        data.get("id", uuid.uuid4().hex[:12]),
        data["artifact_type"],
        data["artifact_id"],
        data["author_id"],
        data.get("author_name", ""),
        data.get("status", "pending_review"),
        data.get("published_at"),
        data["title"],
        data.get("description", ""),
        tags if isinstance(tags, str) else json.dumps(tags),
        data.get("category", "general"),
        data.get("version", "1.0.0"),
        data.get("automated_checks_passed", False),
        data.get("review_notes"),
        data.get("bundle_id"),
        data.get("source_url"),
        data.get("forked_from"),
        bundle_manifest,
    )
    return _decode_row(row)


# ── Read ──────────────────────────────────────────────────────────────────


async def get_publication(pool: asyncpg.Pool, publication_id: str) -> dict | None:
    """Get a single community publication by ID."""
    row = await pool.fetchrow(
        "SELECT * FROM community_publications WHERE id = $1", publication_id
    )
    if not row:
        return None
    return _decode_row(row)


async def list_publications(
    pool: asyncpg.Pool,
    *,
    artifact_type: str | None = None,
    category: str | None = None,
    search: str | None = None,
    sort: str = "popular",
    page: int = 1,
    per_page: int = 20,
) -> list[dict]:
    """List published community artifacts with filtering, search, sort, and pagination."""
    conditions: list[str] = ["status = 'published'"]
    params: list[object] = []
    idx = 1

    if artifact_type:
        conditions.append(f"artifact_type = ${idx}")
        params.append(artifact_type)
        idx += 1

    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1

    if search:
        conditions.append(f"(title ILIKE ${idx} OR description ILIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1

    where = " WHERE " + " AND ".join(conditions)

    sort_clause = {
        "popular": "install_count DESC, created_at DESC",
        "recent": "created_at DESC",
        "rating": "CASE WHEN rating_count > 0 THEN rating_sum / rating_count ELSE 0 END DESC, install_count DESC",
    }.get(sort, "install_count DESC, created_at DESC")

    offset = (page - 1) * per_page
    query = (
        f"SELECT * FROM community_publications{where}"
        f" ORDER BY {sort_clause}"
        f" LIMIT ${idx} OFFSET ${idx + 1}"
    )
    params.extend([per_page, offset])

    rows = await pool.fetch(query, *params)
    return [_decode_row(r) for r in rows]


async def list_publications_by_author(pool: asyncpg.Pool, author_id: str) -> dict[str, list[dict]]:
    """List publications by author, grouped by status."""
    rows = await pool.fetch(
        "SELECT * FROM community_publications WHERE author_id = $1 ORDER BY updated_at DESC",
        author_id,
    )
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        d = _decode_row(r)
        s = d.get("status", "pending_review")
        grouped.setdefault(s, []).append(d)
    return grouped


async def count_publications(
    pool: asyncpg.Pool,
    *,
    artifact_type: str | None = None,
    category: str | None = None,
    search: str | None = None,
) -> int:
    """Count published community artifacts matching filters."""
    conditions: list[str] = ["status = 'published'"]
    params: list[object] = []
    idx = 1

    if artifact_type:
        conditions.append(f"artifact_type = ${idx}")
        params.append(artifact_type)
        idx += 1
    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if search:
        conditions.append(f"(title ILIKE ${idx} OR description ILIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1

    where = " WHERE " + " AND ".join(conditions)
    return await pool.fetchval(f"SELECT COUNT(*) FROM community_publications{where}", *params)


# ── Update ────────────────────────────────────────────────────────────────


async def update_publication_status(pool: asyncpg.Pool, publication_id: str, new_status: str) -> bool:
    """Update a publication's lifecycle status."""
    result = await pool.execute(
        "UPDATE community_publications SET status = $1, updated_at = now() WHERE id = $2",
        new_status,
        publication_id,
    )
    return result == "UPDATE 1"


async def increment_install_count(pool: asyncpg.Pool, publication_id: str) -> None:
    """Atomically increment install count."""
    await pool.execute(
        "UPDATE community_publications SET install_count = install_count + 1 WHERE id = $1",
        publication_id,
    )


async def increment_flag_count(pool: asyncpg.Pool, publication_id: str) -> int:
    """Atomically increment flag count and return new value."""
    return await pool.fetchval(
        "UPDATE community_publications SET flag_count = flag_count + 1 WHERE id = $1 RETURNING flag_count",
        publication_id,
    )


# ── Ratings ───────────────────────────────────────────────────────────────


async def upsert_rating(
    pool: asyncpg.Pool, publication_id: str, user_id: str, rating: int
) -> float:
    """Upsert a user's rating for a publication. Returns new average."""
    await pool.execute(
        """INSERT INTO community_ratings (publication_id, user_id, rating)
           VALUES ($1, $2, $3)
           ON CONFLICT (publication_id, user_id) DO UPDATE SET rating = $3""",
        publication_id,
        user_id,
        rating,
    )
    # Recompute aggregates
    row = await pool.fetchrow(
        """UPDATE community_publications SET
               rating_sum = sub.s, rating_count = sub.c, updated_at = now()
           FROM (SELECT COALESCE(SUM(rating), 0) AS s, COUNT(*) AS c
                 FROM community_ratings WHERE publication_id = $1) sub
           WHERE id = $1
           RETURNING CASE WHEN rating_count > 0
                         THEN rating_sum / rating_count ELSE 0 END AS avg""",
        publication_id,
    )
    return row["avg"] if row else 0.0


# ── Flags ─────────────────────────────────────────────────────────────────


async def create_flag(
    pool: asyncpg.Pool, publication_id: str, user_id: str, reason: str
) -> int:
    """Create a flag and return new flag count. Returns 0 if already flagged by user."""
    try:
        await pool.execute(
            """INSERT INTO community_flags (id, publication_id, user_id, reason)
               VALUES ($1, $2, $3, $4)""",
            uuid.uuid4().hex[:12],
            publication_id,
            user_id,
            reason,
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            return 0
        raise  # Re-raise unexpected errors
    return await increment_flag_count(pool, publication_id)
