import json
import time
from datetime import datetime, timedelta

from sqlalchemy import select, func, text

from app.extensions import db
from app.models.member import Member, Tag, member_tags
from app.models.search import SearchLog


class SearchService:

    @staticmethod
    def _get_config(key, default):
        """Read a search config value from SystemConfig table, falling back to default."""
        try:
            from app.models.config import SystemConfig
            row = db.session.query(SystemConfig).filter_by(key=key).first()
            if row and row.value:
                return int(row.value)
        except Exception:
            pass
        return int(default)

    @staticmethod
    def search(query, status=None, membership_type=None, tag_name=None,
               page=1, per_page=None, user_id=None, date_from=None, date_to=None):
        """Full-text search across members with filtering.
        Returns dict with items, total, highlights, and latency."""
        if per_page is None:
            per_page = SearchService._get_config('search_results_per_page', 20)
        start = time.time()
        query_str = query.strip() if query else ''

        filters = {}
        if status:
            filters['status'] = status
        if membership_type:
            filters['membership_type'] = membership_type
        if tag_name:
            filters['tag'] = tag_name

        if query_str:
            results, total, highlights = SearchService._fts_search(
                query_str, status, membership_type, tag_name, page, per_page,
                date_from=date_from, date_to=date_to,
            )
        else:
            results, total, highlights = SearchService._filtered_list(
                status, membership_type, tag_name, page, per_page,
                date_from=date_from, date_to=date_to,
            )

        latency_ms = (time.time() - start) * 1000

        # Log the search
        if query_str:
            SearchService._log_search(query_str, total, filters, user_id, latency_ms)

        # Record SLA metric
        try:
            from app.services.sla_service import SLAService
            SLAService.record_metric(
                'search_latency', latency_ms,
                endpoint='/search',
                details=f'query="{query_str}", results={total}',
                user_id=user_id,
            )
        except Exception:
            pass

        from app.services.member_service import PaginatedResult
        return {
            'results': PaginatedResult(results, total, page, per_page),
            'highlights': highlights,
            'latency_ms': latency_ms,
            'query': query_str,
        }

    @staticmethod
    def _fts_search(query_str, status, membership_type, tag_name, page, per_page,
                    date_from=None, date_to=None):
        """Perform FTS5 search and return matching members with highlights."""
        fts_query = SearchService._prepare_fts_query(query_str)

        conn = db.engine.raw_connection()
        cursor = conn.cursor()

        try:
            sql = """
                SELECT rowid,
                       snippet(members_fts, 0, '<mark>', '</mark>', '...', 32) as first_name_hl,
                       snippet(members_fts, 1, '<mark>', '</mark>', '...', 32) as last_name_hl,
                       snippet(members_fts, 2, '<mark>', '</mark>', '...', 32) as email_hl,
                       snippet(members_fts, 4, '<mark>', '</mark>', '...', 32) as org_hl,
                       snippet(members_fts, 5, '<mark>', '</mark>', '...', 64) as notes_hl,
                       rank
                FROM members_fts
                WHERE members_fts MATCH ?
                ORDER BY rank
            """
            cursor.execute(sql, (fts_query,))
            fts_rows = cursor.fetchall()
        finally:
            conn.close()

        if not fts_rows:
            return [], 0, {}

        member_ids = [row[0] for row in fts_rows]
        highlights = {}
        for row in fts_rows:
            highlights[row[0]] = {
                'first_name': row[1],
                'last_name': row[2],
                'email': row[3],
                'organization': row[4],
                'notes': row[5],
            }

        # Build SQLAlchemy query with filters
        query = select(Member).where(Member.id.in_(member_ids))
        query = query.where(Member.is_archived == False)  # noqa: E712

        if status:
            query = query.where(Member.status == status)
        if membership_type:
            query = query.where(Member.membership_type == membership_type)
        if tag_name:
            query = query.join(Member.tags).where(Tag.name == tag_name)
        if date_from:
            query = query.where(Member.created_at >= date_from)
        if date_to:
            query = query.where(Member.created_at <= date_to)

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = db.session.execute(count_q).scalar()

        # Paginate — preserve FTS rank ordering
        members_all = db.session.execute(query).scalars().all()
        id_order = {mid: i for i, mid in enumerate(member_ids)}
        members_all.sort(key=lambda m: id_order.get(m.id, 999999))

        start_idx = (page - 1) * per_page
        members = members_all[start_idx:start_idx + per_page]

        return members, total, highlights

    @staticmethod
    def _filtered_list(status, membership_type, tag_name, page, per_page,
                       date_from=None, date_to=None):
        """List members with filters but no FTS query."""
        query = select(Member).where(Member.is_archived == False)  # noqa: E712

        if status:
            query = query.where(Member.status == status)
        if membership_type:
            query = query.where(Member.membership_type == membership_type)
        if tag_name:
            query = query.join(Member.tags).where(Tag.name == tag_name)
        if date_from:
            query = query.where(Member.created_at >= date_from)
        if date_to:
            query = query.where(Member.created_at <= date_to)

        count_q = select(func.count()).select_from(query.subquery())
        total = db.session.execute(count_q).scalar()

        query = query.order_by(Member.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        members = db.session.execute(query).scalars().all()

        return members, total, {}

    @staticmethod
    def _prepare_fts_query(query_str):
        """Prepare a safe FTS5 query string."""
        cleaned = query_str.replace('"', '').replace("'", '')
        for ch in ['(', ')', '{', '}', ':', '^', '-', '~', '*', '+']:
            cleaned = cleaned.replace(ch, ' ')

        tokens = cleaned.split()
        if not tokens:
            return '""'

        parts = []
        for token in tokens:
            token = token.strip()
            if token:
                parts.append(f'"{token}"*')

        return ' '.join(parts)

    @staticmethod
    def _log_search(query_str, results_count, filters, user_id, latency_ms):
        log = SearchLog(
            query=query_str[:500],
            results_count=results_count,
            filters=json.dumps(filters) if filters else None,
            user_id=user_id,
            latency_ms=latency_ms,
        )
        db.session.add(log)
        db.session.commit()

    @staticmethod
    def get_trending(limit=None, days=None):
        """Get trending search queries from the last N days."""
        if limit is None:
            limit = SearchService._get_config('search_trending_limit', 10)
        if days is None:
            days = SearchService._get_config('search_trending_days', 7)
        since = datetime.utcnow() - timedelta(days=days)
        results = db.session.execute(
            select(
                SearchLog.query,
                func.count(SearchLog.id).label('count'),
                func.avg(SearchLog.results_count).label('avg_results'),
            )
            .where(SearchLog.created_at >= since)
            .group_by(SearchLog.query)
            .order_by(func.count(SearchLog.id).desc())
            .limit(limit)
        ).all()

        return [{'query': r[0], 'count': r[1], 'avg_results': round(r[2] or 0)} for r in results]

    @staticmethod
    def get_recommendations(user_id=None, limit=None):
        if limit is None:
            limit = SearchService._get_config('search_recommendations_limit', 5)
        """Generate search recommendations based on user's recent searches
        and popular queries they haven't tried."""
        recommendations = []

        if user_id:
            recent = db.session.execute(
                select(SearchLog.query)
                .where(SearchLog.user_id == user_id)
                .order_by(SearchLog.created_at.desc())
                .limit(5)
            ).scalars().all()

            if recent:
                user_queries = set(recent)
                trending = SearchService.get_trending(limit=20)
                for t in trending:
                    if t['query'] not in user_queries and len(recommendations) < limit:
                        recommendations.append({
                            'query': t['query'],
                            'reason': f"Trending ({t['count']} searches)",
                        })

        if len(recommendations) < limit:
            trending = SearchService.get_trending(limit=limit)
            existing = {r['query'] for r in recommendations}
            for t in trending:
                if t['query'] not in existing and len(recommendations) < limit:
                    recommendations.append({
                        'query': t['query'],
                        'reason': 'Popular search',
                    })

        if len(recommendations) < limit:
            orgs = db.session.execute(
                select(Member.organization, func.count(Member.id))
                .where(Member.organization.isnot(None), Member.is_archived == False)  # noqa: E712
                .group_by(Member.organization)
                .order_by(func.count(Member.id).desc())
                .limit(limit - len(recommendations))
            ).all()

            existing = {r['query'] for r in recommendations}
            for org, count in orgs:
                if org and org not in existing:
                    recommendations.append({
                        'query': org,
                        'reason': f'{count} member(s) in this organization',
                    })

        return recommendations[:limit]

    @staticmethod
    def get_nearby_tags(query_str, limit=5):
        """Get tags that are related to the search query for no-result recommendations."""
        if not query_str:
            return []
        pattern = f'%{query_str}%'
        tags = db.session.execute(
            select(Tag)
            .where(Tag.name.ilike(pattern))
            .limit(limit)
        ).scalars().all()

        if not tags:
            tags = db.session.execute(
                select(Tag).order_by(Tag.name).limit(limit)
            ).scalars().all()

        return tags

    @staticmethod
    def get_recent_members(limit=5):
        """Get recently added members for no-result recommendations."""
        return db.session.execute(
            select(Member)
            .where(Member.is_archived == False)  # noqa: E712
            .order_by(Member.created_at.desc())
            .limit(limit)
        ).scalars().all()

    @staticmethod
    def get_search_logs(limit=50):
        return db.session.execute(
            select(SearchLog)
            .order_by(SearchLog.created_at.desc())
            .limit(limit)
        ).scalars().all()
