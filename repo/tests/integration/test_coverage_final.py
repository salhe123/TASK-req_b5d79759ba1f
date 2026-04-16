"""Final coverage boost tests for middleware, cleansing normalizers, dispatch flows."""
import io
import json
import pytest
from datetime import datetime, timedelta

from app.extensions import db
from app.services.auth_service import AuthService
from app.services.member_service import MemberService
from app.services.address_service import AddressService, ServiceAreaService
from app.services.cleansing_service import CleansingService
from app.services.encryption_service import EncryptionService


class TestMiddlewareSensitiveReauth:
    """Cover sensitive_action_reauth decorator paths."""

    def test_sensitive_reauth_not_triggered_when_recently_active(self, auth_client, app):
        """Active user should not be forced to reauth."""
        r = auth_client.get('/admin/search-config')
        assert r.status_code == 200

    def test_sensitive_reauth_blocks_after_inactivity(self, app, client, db, seed_roles):
        """User inactive beyond timeout should be redirected to reauth."""
        user = AuthService.create_user('inact', 'inact@t.com', 'pass', 'admin')
        client.post('/auth/login', data={'username': 'inact', 'password': 'pass'})
        # Simulate inactivity
        user.last_activity = datetime.utcnow() - timedelta(minutes=60)
        db.session.commit()
        r = client.get('/admin/search-config')
        # Should redirect to reauth
        assert r.status_code == 302
        assert 'reauth' in r.headers.get('Location', '')


class TestCleansingNormalizersCoverage:
    """Cover more normalizer edge cases."""

    def test_normalize_datetime_iso(self, app, admin_user):
        r = CleansingService._normalize_datetime('2024-06-15T14:30:00')
        assert '06/15/2024' in r

    def test_normalize_datetime_mdy(self, app, admin_user):
        r = CleansingService._normalize_datetime('12/25/2023')
        assert '12/25/2023' in r

    def test_normalize_datetime_invalid(self, app, admin_user):
        r = CleansingService._normalize_datetime('not-a-date')
        assert r == 'not-a-date'

    def test_normalize_currency_no_match(self, app, admin_user):
        r = CleansingService._normalize_currency_to_usd('free')
        assert r == 'free'

    def test_normalize_imperial_celsius(self, app, admin_user):
        r = CleansingService._normalize_to_imperial('100 c')
        assert 'f' in r.lower()

    def test_normalize_imperial_unknown_unit(self, app, admin_user):
        r = CleansingService._normalize_to_imperial('50 xyz')
        assert r == '50 xyz'

    def test_normalize_place_unknown(self, app, admin_user):
        r = CleansingService._normalize_place_name('some random city')
        assert r == 'Some Random City'  # titlecased

    def test_outlier_detection_no_numeric(self, app, admin_user):
        rows = [{'name': 'a'}, {'name': 'b'}, {'name': 'c'}]
        clean, flagged = CleansingService._detect_outliers(rows)
        assert len(flagged) == 0

    def test_outlier_detection_empty(self, app, admin_user):
        clean, flagged = CleansingService._detect_outliers([])
        assert clean == []
        assert flagged == []

    def test_similarity_identical(self, app, admin_user):
        assert CleansingService._similarity('abc', 'abc') == 1.0

    def test_similarity_empty(self, app, admin_user):
        assert CleansingService._similarity('', 'abc') == 0.0

    def test_field_mapping(self, app, admin_user):
        rows = [{'A': '1', 'B': '2'}]
        result = CleansingService._apply_field_mapping(rows, {'A': 'alpha'})
        assert 'alpha' in result[0]
        assert result[0]['alpha'] == '1'

    def test_missing_rules_flag(self, app, admin_user):
        rows = [{'name': 'x', 'email': ''}]
        clean, flagged = CleansingService._apply_missing_rules(
            rows, {'email': {'action': 'flag'}}
        )
        assert len(flagged) == 1

    def test_dedup_empty_fields(self, app, admin_user):
        rows = [{'a': '1'}, {'a': '2'}]
        unique, dups = CleansingService._deduplicate(rows, [], 1.0)
        assert len(unique) == 2


class TestEncryptionService:
    def test_encrypt_decrypt(self, app):
        plain = 'sensitive data 123'
        enc = EncryptionService.encrypt(plain)
        assert enc != plain
        dec = EncryptionService.decrypt(enc)
        assert dec == plain

    def test_encrypt_empty(self, app):
        assert EncryptionService.encrypt('') == ''
        assert EncryptionService.encrypt(None) is None

    def test_is_encrypted(self, app):
        enc = EncryptionService.encrypt('test')
        assert EncryptionService.is_encrypted(enc) is True
        assert EncryptionService.is_encrypted('not encrypted') is False

    def test_mask(self, app):
        assert EncryptionService.mask('1234567890') == '******7890'
        assert EncryptionService.mask('ab') == '**'


class TestDispatchFlowsCoverage:
    def test_address_htmx_list(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'HX', 'last_name': 'Addr', 'email': 'hxa@t.com'}, created_by=1)
        r = auth_client.get(f'/dispatch/members/{m.id}/addresses',
                            headers={'HX-Request': 'true'})
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data

    def test_address_create_post(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'CP', 'last_name': 'Addr', 'email': 'cpa@t.com'}, created_by=1)
        r = auth_client.post(f'/dispatch/members/{m.id}/addresses/new', data={
            'street': '10 Main', 'city': 'NYC', 'state': 'NY', 'zip_code': '10001',
            'label': 'primary',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_address_edit_post(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'EP', 'last_name': 'Addr', 'email': 'epa@t.com'}, created_by=1)
        addr, _ = AddressService.create(m.id, {
            'street': '1 St', 'city': 'B', 'state': 'C', 'zip_code': '00000'})
        r = auth_client.post(f'/dispatch/addresses/{addr.id}/edit', data={
            'street': '2 St', 'city': 'B', 'state': 'C', 'zip_code': '00000',
            'label': 'primary', 'version': str(addr.version),
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_address_delete_htmx(self, auth_client, app, db):
        m, _ = MemberService.create(
            {'first_name': 'DH', 'last_name': 'Addr', 'email': 'dha@t.com'}, created_by=1)
        addr, _ = AddressService.create(m.id, {
            'street': '1 D', 'city': 'X', 'state': 'Y', 'zip_code': '11111'})
        r = auth_client.post(f'/dispatch/addresses/{addr.id}/delete',
                             headers={'HX-Request': 'true'})
        assert r.status_code == 200

    def test_service_area_edit_post(self, auth_client, app, db):
        area, _ = ServiceAreaService.create({
            'name': 'EdPost', 'area_type': 'region', 'region': 'north'})
        r = auth_client.post(f'/dispatch/service-areas/{area.id}/edit', data={
            'name': 'EdPost', 'area_type': 'region', 'region': 'south',
            'is_active': '1', 'version': str(area.version),
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_site_address_htmx_delete(self, auth_client, app, db):
        from app.services.address_service import SiteAddressService
        site, _ = SiteAddressService.create({
            'name': 'HXDel', 'street': '1 A', 'city': 'B',
            'state': 'C', 'zip_code': '99999'})
        r = auth_client.post(f'/dispatch/site-addresses/{site.id}/delete',
                             headers={'HX-Request': 'true'}, follow_redirects=True)
        assert r.status_code == 200


class TestMemberRoutesCoverage:
    """Cover all uncovered lines in app/routes/members.py."""

    def test_create_get_page(self, auth_client):
        """Line 90: GET /members/new renders form."""
        r = auth_client.get('/members/new')
        assert r.status_code == 200
        assert b'Create Member' in r.data

    def test_create_htmx_error(self, auth_client, app):
        """Line 83: HTMX POST with validation error returns partial."""
        r = auth_client.post('/members/new', data={
            'first_name': '', 'last_name': '', 'email': '',
        }, headers={'HX-Request': 'true'})
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data

    def test_create_non_htmx_error(self, auth_client, app):
        """Line 85: non-HTMX POST with validation error returns full page."""
        r = auth_client.post('/members/new', data={
            'first_name': '', 'last_name': '', 'email': '',
        })
        assert r.status_code == 200
        assert b'<!DOCTYPE' in r.data

    def test_detail_not_found(self, auth_client):
        """Line 99-100: member not found redirects."""
        r = auth_client.get('/members/99999', follow_redirects=True)
        assert r.status_code == 200

    def test_edit_get_page(self, auth_client, app, db):
        """Lines 168-178: GET edit page populates data dict."""
        m, _ = MemberService.create(
            {'first_name': 'Ed', 'last_name': 'Get', 'email': 'edget@t.com'},
            created_by=1, tag_names=['priority'])
        r = auth_client.get(f'/members/{m.id}/edit')
        assert r.status_code == 200
        assert b'edget@t.com' in r.data
        assert b'priority' in r.data

    def test_edit_not_found(self, auth_client):
        """Line 127-128: edit nonexistent member."""
        r = auth_client.get('/members/99999/edit', follow_redirects=True)
        assert r.status_code == 200

    def test_edit_htmx_error(self, auth_client, app, db):
        """Lines 159-163: HTMX edit with error returns partial."""
        m, _ = MemberService.create(
            {'first_name': 'HXE', 'last_name': 'T', 'email': 'hxe@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/edit', data={
            'first_name': '', 'last_name': '', 'email': '',
            'version': str(m.version),
        }, headers={'HX-Request': 'true'})
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data

    def test_edit_non_htmx_error(self, auth_client, app, db):
        """Line 163: non-HTMX edit with error returns full page."""
        m, _ = MemberService.create(
            {'first_name': 'NHE', 'last_name': 'T', 'email': 'nhe@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/edit', data={
            'first_name': '', 'last_name': '', 'email': '',
            'version': str(m.version),
        })
        assert r.status_code == 200

    def test_edit_optimistic_lock_conflict(self, auth_client, app, db):
        """Lines 153-156: stale version triggers OptimisticLockError."""
        m, _ = MemberService.create(
            {'first_name': 'OL', 'last_name': 'T', 'email': 'ol@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/edit', data={
            'first_name': 'OL', 'last_name': 'T', 'email': 'ol@t.com',
            'version': '999',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'modified by another' in r.data.lower()

    def test_delete_error_flash(self, auth_client, app, db):
        """Line 188: delete nonexistent shows error."""
        r = auth_client.post('/members/99999/delete', follow_redirects=True)
        assert r.status_code == 200

    def test_delete_htmx(self, auth_client, app, db):
        """Line 192-193: delete via HTMX."""
        m, _ = MemberService.create(
            {'first_name': 'DH', 'last_name': 'T', 'email': 'dh@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/delete',
                             headers={'HX-Request': 'true'})
        assert r.status_code == 302

    def test_restore_error(self, auth_client):
        """Line 205: restore nonexistent shows error."""
        r = auth_client.post('/members/99999/restore', follow_redirects=True)
        assert r.status_code == 200

    def test_validate_email_no_at(self, auth_client, app):
        """Line 224: email without @ is invalid."""
        r = auth_client.post('/members/validate-field', data={
            'field': 'email', 'value': 'bademail',
        })
        assert b'Invalid email' in r.data

    def test_validate_email_with_member_id(self, auth_client, app, db):
        """Line 232: email check excludes current member_id."""
        m, _ = MemberService.create(
            {'first_name': 'EM', 'last_name': 'T', 'email': 'em@t.com'}, created_by=1)
        r = auth_client.post('/members/validate-field', data={
            'field': 'email', 'value': 'em@t.com', 'member_id': str(m.id),
        })
        assert b'already exists' not in r.data

    def test_validate_last_name_empty(self, auth_client, app):
        """Lines 239-241: empty last_name returns error."""
        r = auth_client.post('/members/validate-field', data={
            'field': 'last_name', 'value': '',
        })
        assert b'required' in r.data.lower()

    def test_tag_empty_name(self, auth_client, app, db):
        """Line 254: empty tag name flashes error."""
        m, _ = MemberService.create(
            {'first_name': 'T', 'last_name': 'T', 'email': 'tg@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/tags', data={'tag_name': ''},
                             follow_redirects=True)
        assert r.status_code == 200

    def test_tag_add_htmx(self, auth_client, app, db):
        """Line 260-262: add tag via HTMX returns partial."""
        m, _ = MemberService.create(
            {'first_name': 'TH', 'last_name': 'T', 'email': 'th@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/tags', data={'tag_name': 'new-tag'},
                             headers={'HX-Request': 'true'})
        assert r.status_code == 200
        assert b'<!DOCTYPE' not in r.data

    def test_tag_add_non_htmx(self, auth_client, app, db):
        """Line 264: add tag without HTMX redirects."""
        m, _ = MemberService.create(
            {'first_name': 'TN', 'last_name': 'T', 'email': 'tn@t.com'}, created_by=1)
        r = auth_client.post(f'/members/{m.id}/tags', data={'tag_name': 'another'})
        assert r.status_code == 302

    def test_remove_tag_htmx(self, auth_client, app, db):
        """Line 273-275: remove tag via HTMX."""
        m, _ = MemberService.create(
            {'first_name': 'RH', 'last_name': 'T', 'email': 'rh@t.com'},
            created_by=1, tag_names=['vip'])
        r = auth_client.post(f'/members/{m.id}/tags/vip/remove',
                             headers={'HX-Request': 'true'})
        assert r.status_code == 200

    def test_remove_tag_non_htmx(self, auth_client, app, db):
        """Line 277: remove tag without HTMX redirects."""
        m, _ = MemberService.create(
            {'first_name': 'RN', 'last_name': 'T', 'email': 'rn@t.com'},
            created_by=1, tag_names=['temp'])
        r = auth_client.post(f'/members/{m.id}/tags/temp/remove')
        assert r.status_code == 302
