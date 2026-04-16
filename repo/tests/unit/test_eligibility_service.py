import pytest
from app.services.member_service import MemberService
from app.services.workflow_service import WorkflowService
from app.services.address_service import AddressService, ServiceAreaService, EligibilityService


class TestEligibilityService:

    def _setup(self, app, admin_user):
        m, _ = MemberService.create({
            'first_name': 'E', 'last_name': 'Test', 'email': 'e@t.com',
        }, created_by=1)
        WorkflowService.execute(m.id, 'JOIN', performed_by=1)
        return m

    def test_region_eligibility(self, app, admin_user):
        m = self._setup(app, admin_user)
        AddressService.create(m.id, {
            'street': '1 Main', 'city': 'Boston', 'state': 'MA',
            'zip_code': '02101', 'region': 'northeast', 'is_primary': True,
        })
        ServiceAreaService.create({
            'name': 'NE Region', 'area_type': 'region',
            'region': 'northeast', 'is_active': True,
        })
        eligible, reason, log = EligibilityService.check_eligibility(m.id, checked_by=1)
        assert eligible
        assert 'Region match' in reason
        assert log.is_eligible

    def test_radius_eligibility(self, app, admin_user):
        m = self._setup(app, admin_user)
        addr, _ = AddressService.create(m.id, {
            'street': '1 Main', 'city': 'Chicago', 'state': 'IL',
            'zip_code': '60601', 'latitude': 41.88, 'longitude': -87.63,
            'is_primary': True,
        })
        ServiceAreaService.create({
            'name': 'Chicago Metro', 'area_type': 'radius',
            'center_latitude': 41.88, 'center_longitude': -87.63,
            'radius_miles': 25.0, 'is_active': True,
        })
        eligible, reason, _ = EligibilityService.check_eligibility(m.id, addr.id, checked_by=1)
        assert eligible
        assert 'miles' in reason

    def test_out_of_range(self, app, admin_user):
        m = self._setup(app, admin_user)
        addr, _ = AddressService.create(m.id, {
            'street': '1 Far', 'city': 'Denver', 'state': 'CO',
            'zip_code': '80201', 'latitude': 39.74, 'longitude': -104.99,
            'is_primary': True,
        })
        ServiceAreaService.create({
            'name': 'Small Area', 'area_type': 'radius',
            'center_latitude': 41.88, 'center_longitude': -87.63,
            'radius_miles': 10.0, 'is_active': True,
        })
        eligible, reason, _ = EligibilityService.check_eligibility(m.id, checked_by=1)
        assert not eligible

    def test_no_address(self, app, admin_user):
        m = self._setup(app, admin_user)
        eligible, reason, _ = EligibilityService.check_eligibility(m.id, checked_by=1)
        assert not eligible
        assert 'No address' in reason

    def test_inactive_member_ineligible(self, app, admin_user):
        m = self._setup(app, admin_user)
        WorkflowService.execute(m.id, 'DEACTIVATE', performed_by=1)
        eligible, reason, _ = EligibilityService.check_eligibility(m.id, checked_by=1)
        assert not eligible
        assert 'not eligible' in reason.lower()

    def test_eligibility_logging(self, app, admin_user):
        m = self._setup(app, admin_user)
        EligibilityService.check_eligibility(m.id, checked_by=1)
        logs = EligibilityService.get_logs(member_id=m.id)
        assert len(logs) >= 1

    def test_haversine_calculation(self, app):
        dist = EligibilityService._haversine(40.7128, -74.0060, 34.0522, -118.2437)
        assert 2440 < dist < 2470  # NYC to LA ~2450 miles

    def test_address_crud(self, app, admin_user):
        m = self._setup(app, admin_user)
        addr, _ = AddressService.create(m.id, {
            'street': '1 Test', 'city': 'X', 'state': 'Y', 'zip_code': '00000',
        })
        assert addr.id is not None
        updated, _ = AddressService.update(addr.id, {
            'street': 'Updated', 'city': 'X', 'state': 'Y', 'zip_code': '00000',
        })
        assert updated.street == 'Updated'
        ok, _ = AddressService.delete(addr.id)
        assert ok
