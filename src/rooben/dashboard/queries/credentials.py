"""Credential CRUD queries."""

from __future__ import annotations

import asyncpg

from rooben.dashboard.credentials import decrypt_value, encrypt_value


async def list_credentials(
    pool: asyncpg.Pool,
    integration_name: str | None = None,
    user_context: dict | None = None,
) -> list[dict]:
    """List credentials with masked values."""
    if integration_name:
        rows = await pool.fetch(
            """SELECT id, integration_name, env_var_name, credential_type, created_at, updated_at
                FROM credentials WHERE integration_name = $1
                ORDER BY integration_name, env_var_name""",
            integration_name,
        )
    else:
        rows = await pool.fetch(
            """SELECT id, integration_name, env_var_name, credential_type, created_at, updated_at
                FROM credentials ORDER BY integration_name, env_var_name"""
        )
    return [{**dict(r), "value": "****"} for r in rows]


async def upsert_credential(
    pool: asyncpg.Pool,
    id: str,
    integration_name: str,
    env_var_name: str,
    value: str,
    credential_type: str = "integration",
) -> dict:
    """Create or update a credential."""
    encrypted = encrypt_value(value)
    row = await pool.fetchrow(
        """INSERT INTO credentials (id, integration_name, env_var_name, encrypted_value, credential_type)
           VALUES ($1, $2, $3, $4, $5)
           ON CONFLICT (integration_name, env_var_name)
           DO UPDATE SET encrypted_value = $4, credential_type = $5, updated_at = now()
           RETURNING id, integration_name, env_var_name, credential_type, created_at, updated_at""",
        id, integration_name, env_var_name, encrypted, credential_type,
    )
    return {**dict(row), "value": "****"}


async def delete_credential(pool: asyncpg.Pool, id: str) -> bool:
    """Delete a credential by ID. Returns True if deleted."""
    result = await pool.execute("DELETE FROM credentials WHERE id = $1", id)
    return result == "DELETE 1"


async def get_decrypted_credentials(pool: asyncpg.Pool) -> dict[str, str]:
    """Load all credentials as env_var_name -> plaintext for runtime cache."""
    rows = await pool.fetch(
        "SELECT env_var_name, encrypted_value FROM credentials"
    )
    result = {}
    for r in rows:
        try:
            result[r["env_var_name"]] = decrypt_value(r["encrypted_value"])
        except Exception:
            pass  # Skip corrupted entries
    return result
