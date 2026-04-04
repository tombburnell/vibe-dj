"""Mark purchase/search links as broken and repoint ``amazon_url`` when needed."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from track_mapper_api.models.source import SourceTrack

logger = logging.getLogger(__name__)


def _row_broken(row: dict[str, Any]) -> bool:
    return bool(row.get("broken"))


def _row_url(row: dict[str, Any]) -> str:
    u = row.get("url")
    return (u if isinstance(u, str) else "") or ""


def _primary_row_from_track(st: SourceTrack) -> dict[str, Any]:
    return {
        "url": (st.amazon_url or "").strip(),
        "title": st.amazon_link_title,
        "artist": None,
        "match_score": st.amazon_link_match_score,
        "price": st.amazon_price,
        "broken": False,
    }


def _ensure_primary_in_rows(st: SourceTrack, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Legacy JSON omitted the primary URL; merge so stored JSON matches the unified model."""
    primary = (st.amazon_url or "").strip()
    if not primary:
        return rows
    if any(_row_url(r).strip() == primary for r in rows):
        return rows
    head = _primary_row_from_track(st)
    if not head["url"]:
        return rows
    return [head, *rows]


def _first_non_broken(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for r in rows:
        if _row_broken(r):
            continue
        url = _row_url(r).strip()
        if url:
            return r
    return None


async def mark_source_amazon_link_broken(
    db: AsyncSession,
    *,
    user_id: str,
    source_track_id: uuid.UUID,
    url: str,
) -> SourceTrack:
    """Set ``broken`` on the matching candidate row(s); if that URL was primary, advance pointer."""
    target = url.strip()
    if not target:
        raise LookupError("Invalid URL")

    res = await db.execute(
        select(SourceTrack).where(
            SourceTrack.user_id == user_id,
            SourceTrack.id == source_track_id,
        )
    )
    st = res.scalar_one_or_none()
    if st is None:
        raise LookupError("Source track not found")

    raw = st.amazon_candidates_json
    raw_list: list[Any] = raw if isinstance(raw, list) else []

    dict_rows: list[dict[str, Any]] = []
    for item in raw_list:
        if isinstance(item, dict):
            dict_rows.append(dict(item))

    dict_rows = _ensure_primary_in_rows(st, dict_rows)

    matched = False
    for r in dict_rows:
        if _row_url(r).strip() == target:
            r["broken"] = True
            matched = True

    if not matched:
        raise LookupError("Link URL not found for this track")

    st.amazon_candidates_json = dict_rows

    primary_before = (st.amazon_url or "").strip()
    if primary_before == target:
        nxt = _first_non_broken(dict_rows)
        if nxt:
            st.amazon_url = _row_url(nxt).strip() or None
            t_raw = nxt.get("title")
            st.amazon_link_title = t_raw if isinstance(t_raw, str) else None
            ms = nxt.get("match_score")
            if ms is None:
                st.amazon_link_match_score = None
            elif isinstance(ms, (int, float)):
                st.amazon_link_match_score = float(ms)
            else:
                st.amazon_link_match_score = None
            p_raw = nxt.get("price")
            st.amazon_price = p_raw if isinstance(p_raw, str) else None
        else:
            st.amazon_url = None
            st.amazon_link_title = None
            st.amazon_link_match_score = None
            st.amazon_price = None

    await db.flush()
    logger.info(
        "mark_source_amazon_link_broken user=%s source_track_id=%s url=%s",
        user_id,
        source_track_id,
        target,
    )
    return st
