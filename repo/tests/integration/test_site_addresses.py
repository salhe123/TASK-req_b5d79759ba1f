"""Integration tests for site address book CRUD and validation."""
import pytest
from app.services.address_service import SiteAddressService


class TestSiteAddressCRUD:

    def test_list_site_addresses(self, auth_client):
        r = auth_client.get('/dispatch/site-addresses')
        assert r.status_code == 200
        assert b'Site Address Book' in r.data

    def test_create_site_address(self, auth_client, app, db):
        r = auth_client.post('/dispatch/site-addresses/new', data={
            'name': 'HQ Office',
            'street': '100 Main St',
            'city': 'Boston',
            'state': 'MA',
            'zip_code': '02101',
            'country': 'US',
            'region': 'northeast',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'HQ Office' in r.data

    def test_create_site_address_validation_fails(self, auth_client):
        r = auth_client.post('/dispatch/site-addresses/new', data={
            'name': 'Bad',
            'street': '',
            'city': '',
            'state': '',
            'zip_code': '',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'required' in r.data.lower()

    def test_edit_site_address(self, auth_client, app, db):
        site, _ = SiteAddressService.create({
            'name': 'Branch', 'street': '1 Elm', 'city': 'NY',
            'state': 'NY', 'zip_code': '10001',
        })
        r = auth_client.get(f'/dispatch/site-addresses/{site.id}/edit')
        assert r.status_code == 200
        assert b'Branch' in r.data

        r = auth_client.post(f'/dispatch/site-addresses/{site.id}/edit', data={
            'name': 'Branch Updated', 'street': '2 Elm', 'city': 'NY',
            'state': 'NY', 'zip_code': '10001', 'version': str(site.version),
        }, follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(site)
        assert site.name == 'Branch Updated'

    def test_delete_site_address(self, auth_client, app, db):
        site, _ = SiteAddressService.create({
            'name': 'ToDelete', 'street': '99 X', 'city': 'A',
            'state': 'B', 'zip_code': '00000',
        })
        r = auth_client.post(f'/dispatch/site-addresses/{site.id}/delete',
                             follow_redirects=True)
        assert r.status_code == 200
        assert SiteAddressService.get(site.id) is None

    def test_optimistic_lock_conflict(self, auth_client, app, db):
        site, _ = SiteAddressService.create({
            'name': 'Locked', 'street': '1 A', 'city': 'B',
            'state': 'C', 'zip_code': '11111',
        })
        # Simulate stale version
        r = auth_client.post(f'/dispatch/site-addresses/{site.id}/edit', data={
            'name': 'Locked', 'street': '1 A', 'city': 'B',
            'state': 'C', 'zip_code': '11111', 'version': '999',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'modified by another' in r.data.lower()
