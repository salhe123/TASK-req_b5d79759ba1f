"""Unit tests for newly added service methods — admin, device admin, site address,
cleansing normalizers, address validation, middleware."""
import pytest
from datetime import datetime
from app.services.admin_service import AdminService
from app.services.device_service import DeviceService
from app.services.address_service import AddressService, SiteAddressService, ServiceAreaService
from app.services.auth_service import AuthService
from app.services.cleansing_service import CleansingService
from app.services.member_service import MemberService


class TestAdminServiceMethods:

    def test_list_users(self, app, admin_user):
        users = AdminService.list_users()
        assert len(users) >= 1

    def test_deactivate_and_activate(self, app, admin_user, db, seed_roles):
        u = AuthService.create_user('adm_test', 'adm@t.com', 'pass', 'operator')
        ok, err = AdminService.deactivate_user(u.id, performed_by=1)
        assert ok is True
        db.session.refresh(u)
        assert u.is_active is False

        ok, err = AdminService.activate_user(u.id, performed_by=1)
        assert ok is True
        db.session.refresh(u)
        assert u.is_active is True

    def test_freeze_and_unfreeze(self, app, admin_user, db, seed_roles):
        u = AuthService.create_user('freeze_test', 'fr@t.com', 'pass', 'operator')
        ok, _ = AdminService.freeze_user(u.id, performed_by=1)
        assert ok
        db.session.refresh(u)
        assert u.locked_until.year > 2050

        ok, _ = AdminService.unfreeze_user(u.id, performed_by=1)
        assert ok
        db.session.refresh(u)
        assert u.locked_until is None

    def test_change_role_valid(self, app, admin_user, db, seed_roles):
        u = AuthService.create_user('role_test', 'ro@t.com', 'pass', 'viewer')
        ok, _ = AdminService.change_user_role(u.id, 'manager', performed_by=1)
        assert ok
        db.session.refresh(u)
        assert u.role == 'manager'

    def test_change_role_invalid(self, app, admin_user, seed_roles):
        u = AuthService.create_user('role_bad', 'rb@t.com', 'pass', 'viewer')
        ok, err = AdminService.change_user_role(u.id, 'superadmin', performed_by=1)
        assert ok is False
        assert 'Invalid role' in err


class TestDeviceAdminMethods:

    def test_admin_list_devices(self, app, admin_user, db):
        DeviceService.register_device(1, 'dev_a', 'Dev A')
        devices = DeviceService.admin_list_devices_for_user(1)
        assert len(devices) >= 1

    def test_admin_revoke_device(self, app, admin_user, db):
        d, _ = DeviceService.register_device(1, 'dev_revoke', 'Revokable')
        ok, _ = DeviceService.admin_revoke_device(d.id, revoked_by=1)
        assert ok
        assert DeviceService.get_device(1, 'dev_revoke') is None

    def test_admin_revoke_all(self, app, admin_user, db):
        DeviceService.register_device(1, 'all1', 'D1')
        DeviceService.register_device(1, 'all2', 'D2')
        ok, _ = DeviceService.admin_revoke_all_devices(1, revoked_by=1)
        assert ok
        assert len(DeviceService.list_devices(1)) == 0


class TestSiteAddressService:

    def test_create_and_list(self, app, admin_user, db):
        site, err = SiteAddressService.create({
            'name': 'Depot', 'street': '10 Oak', 'city': 'Denver',
            'state': 'CO', 'zip_code': '80201',
        })
        assert err is None
        assert site.name == 'Depot'
        assert len(SiteAddressService.list_all()) >= 1

    def test_create_validation_fails(self, app, admin_user):
        _, err = SiteAddressService.create({
            'name': 'Bad', 'street': '', 'city': '', 'state': '', 'zip_code': '',
        })
        assert err is not None
        assert 'required' in err.lower()

    def test_update_with_version(self, app, admin_user, db):
        site, _ = SiteAddressService.create({
            'name': 'V1', 'street': '1 X', 'city': 'Y', 'state': 'Z', 'zip_code': '00000',
        })
        updated, err = SiteAddressService.update(site.id, {
            'name': 'V2', 'street': '2 X', 'city': 'Y', 'state': 'Z', 'zip_code': '00000',
        }, expected_version=site.version)
        assert err is None
        assert updated.name == 'V2'

    def test_delete(self, app, admin_user, db):
        site, _ = SiteAddressService.create({
            'name': 'Del', 'street': '1 A', 'city': 'B', 'state': 'C', 'zip_code': '11111',
        })
        ok, _ = SiteAddressService.delete(site.id)
        assert ok
        assert SiteAddressService.get(site.id) is None


class TestServiceAreaValidation:

    def test_invalid_area_type(self, app, admin_user):
        _, err = ServiceAreaService.create({
            'name': 'Bad Type', 'area_type': 'polygon', 'region': 'x',
        })
        assert err is not None
        assert 'Invalid area type' in err

    def test_region_type_requires_region(self, app, admin_user):
        _, err = ServiceAreaService.create({
            'name': 'No Region', 'area_type': 'region', 'region': '',
        })
        assert err is not None
        assert 'Region is required' in err

    def test_radius_type_requires_coords(self, app, admin_user):
        _, err = ServiceAreaService.create({
            'name': 'No Coords', 'area_type': 'radius',
            'center_latitude': None, 'center_longitude': None,
        })
        assert err is not None
        assert 'latitude' in err.lower()

    def test_negative_radius_rejected(self, app, admin_user):
        _, err = ServiceAreaService.create({
            'name': 'Neg', 'area_type': 'radius',
            'center_latitude': 40.0, 'center_longitude': -74.0,
            'radius_miles': -5,
        })
        assert err is not None
        assert 'Radius' in err


class TestCleansingNormalizers:

    def test_datetime_normalize(self, app, admin_user):
        result = CleansingService._normalize_datetime('2024-01-15')
        assert '01/15/2024' in result

    def test_currency_normalize(self, app, admin_user):
        result = CleansingService._normalize_currency_to_usd('100 eur')
        assert '$' in result

    def test_imperial_normalize(self, app, admin_user):
        result = CleansingService._normalize_to_imperial('10 km')
        assert 'miles' in result

    def test_place_name_normalize(self, app, admin_user):
        assert CleansingService._normalize_place_name('nyc') == 'New York'
        assert CleansingService._normalize_place_name('ca') == 'California'

    def test_outlier_detection(self, app, admin_user):
        rows = [{'val': '10'}, {'val': '12'}, {'val': '11'}, {'val': '13'},
                {'val': '100'}]  # 100 is outlier
        clean, flagged = CleansingService._detect_outliers(rows)
        assert len(flagged) >= 1

    def test_create_with_tags_atomic(self, app, admin_user):
        member, err = MemberService.create(
            {'first_name': 'Atomic', 'last_name': 'Test', 'email': 'atomic@t.com'},
            created_by=1, tag_names=['vip', 'new'],
        )
        assert err is None
        assert len(member.tags) == 2


class TestMemberFieldValidation:

    def test_validate_field_email_duplicate(self, app, auth_client):
        MemberService.create(
            {'first_name': 'A', 'last_name': 'B', 'email': 'dup@test.com'},
            created_by=1,
        )
        r = auth_client.post('/members/validate-field', data={
            'field': 'email', 'value': 'dup@test.com',
        })
        assert b'already exists' in r.data

    def test_validate_field_email_valid(self, app, auth_client):
        r = auth_client.post('/members/validate-field', data={
            'field': 'email', 'value': 'unique@new.com',
        })
        assert b'already exists' not in r.data

    def test_validate_field_first_name_empty(self, app, auth_client):
        r = auth_client.post('/members/validate-field', data={
            'field': 'first_name', 'value': '',
        })
        assert b'required' in r.data.lower()
