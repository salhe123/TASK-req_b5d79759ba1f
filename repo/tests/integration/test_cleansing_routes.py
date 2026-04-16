"""Integration tests for cleansing routes — template CRUD, upload, job view, encryption."""
import io
import json
import pytest
from app.services.cleansing_service import CleansingService
from app.models.cleansing import CleansingJob


class TestCleansingRoutes:

    def test_cleansing_index(self, auth_client):
        r = auth_client.get('/cleansing/')
        assert r.status_code == 200
        assert b'Cleansing' in r.data or b'cleansing' in r.data

    def test_create_template_page(self, auth_client):
        r = auth_client.get('/cleansing/templates/new')
        assert r.status_code == 200
        assert b'Template' in r.data

    def test_create_template_post(self, auth_client, app, db):
        r = auth_client.post('/cleansing/templates/new', data={
            'name': 'RouteTest',
            'description': 'test',
            'field_mapping': '{}',
            'missing_value_rules': '{}',
            'dedup_fields': '[]',
            'dedup_threshold': '1.0',
            'format_rules': '{}',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'RouteTest' in r.data

    def test_view_template(self, auth_client, app, db):
        t, _ = CleansingService.create_template({
            'name': 'ViewT', 'description': 'x',
        }, created_by=1)
        r = auth_client.get(f'/cleansing/templates/{t.id}')
        assert r.status_code == 200
        assert b'ViewT' in r.data

    def test_edit_template(self, auth_client, app, db):
        t, _ = CleansingService.create_template({'name': 'EditT'}, created_by=1)
        r = auth_client.get(f'/cleansing/templates/{t.id}/edit')
        assert r.status_code == 200

        r = auth_client.post(f'/cleansing/templates/{t.id}/edit', data={
            'name': 'EditT', 'description': 'updated',
            'field_mapping': '{}', 'missing_value_rules': '{}',
            'dedup_fields': '[]', 'dedup_threshold': '1.0', 'format_rules': '{}',
        }, follow_redirects=True)
        assert r.status_code == 200

    def test_delete_template(self, auth_client, app, db):
        t, _ = CleansingService.create_template({'name': 'DelT'}, created_by=1)
        r = auth_client.post(f'/cleansing/templates/{t.id}/delete', follow_redirects=True)
        assert r.status_code == 200
        db.session.refresh(t)
        assert t.is_active is False

    def test_upload_page(self, auth_client):
        r = auth_client.get('/cleansing/upload')
        assert r.status_code == 200

    def test_upload_and_view_job(self, auth_client, app, db):
        t, _ = CleansingService.create_template({
            'name': 'UploadT',
            'format_rules': {'email': 'lowercase'},
        }, created_by=1)
        csv = b'email\nTEST@EXAMPLE.COM\n'
        r = auth_client.post('/cleansing/upload', data={
            'template_id': str(t.id),
            'csv_file': (io.BytesIO(csv), 'test.csv'),
        }, content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200

        job = CleansingJob.query.first()
        r = auth_client.get(f'/cleansing/jobs/{job.id}')
        assert r.status_code == 200
        assert b'test@example.com' in r.data
