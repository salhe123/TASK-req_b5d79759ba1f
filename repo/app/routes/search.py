from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.middleware import roles_required
from app.services.search_service import SearchService
from app.services.member_service import MemberService

search_bp = Blueprint('search', __name__, url_prefix='/search')


@search_bp.route('/')
@login_required
def index():
    query = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip() or None
    membership_type = request.args.get('membership_type', '').strip() or None
    tag = request.args.get('tag', '').strip() or None
    page = request.args.get('page', 1, type=int)

    date_from = None
    date_to = None
    date_from_str = request.args.get('date_from', '').strip()
    date_to_str = request.args.get('date_to', '').strip()
    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
        except ValueError:
            pass
    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            pass

    result = None
    if query or status or membership_type or tag or date_from or date_to:
        result = SearchService.search(
            query, status=status, membership_type=membership_type,
            tag_name=tag, page=page, user_id=current_user.id,
            date_from=date_from, date_to=date_to,
        )

    trending = SearchService.get_trending()
    recommendations = SearchService.get_recommendations(user_id=current_user.id)
    nearby_tags = SearchService.get_nearby_tags(query) if (result and result['results'].total == 0 and query) else []
    recent_members = SearchService.get_recent_members() if (result and result['results'].total == 0) else []
    tags = MemberService.get_all_tags()

    # Log view action for audit/anomaly detection
    try:
        from app.services.audit_service import AuditService
        AuditService.log(
            action='search',
            category='search',
            entity_type='member',
            user_id=current_user.id,
            username=current_user.username,
            details=f'query="{query}"' if query else 'browse filters',
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning('Audit log failed for search')

    if request.headers.get('HX-Request'):
        return render_template('search/partials/search_results.html',
                               result=result, query=query, status=status,
                               membership_type=membership_type, tag=tag,
                               nearby_tags=nearby_tags, recent_members=recent_members)

    return render_template('search/index.html',
                           result=result, query=query, status=status,
                           membership_type=membership_type, tag=tag,
                           date_from=date_from_str, date_to=date_to_str,
                           trending=trending, recommendations=recommendations,
                           nearby_tags=nearby_tags, recent_members=recent_members,
                           tags=tags)


@search_bp.route('/logs')
@login_required
@roles_required('admin')
def logs():
    search_logs = SearchService.get_search_logs(limit=100)
    return render_template('search/logs.html', logs=search_logs)
