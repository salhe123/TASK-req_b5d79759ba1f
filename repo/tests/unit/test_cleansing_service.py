import json
import pytest
from app.services.cleansing_service import CleansingService


class TestCleansingService:

    def _create_template(self, app, admin_user):
        t, _ = CleansingService.create_template({
            'name': 'Test',
            'field_mapping': {'Name': 'name', 'Email': 'email'},
            'missing_value_rules': {'email': {'action': 'skip'}, 'phone': {'action': 'default', 'value': 'N/A'}},
            'dedup_fields': ['email'],
            'dedup_threshold': 1.0,
            'format_rules': {'email': 'lowercase', 'name': 'titlecase'},
        }, created_by=1)
        return t

    def test_create_template(self, app, admin_user):
        t = self._create_template(app, admin_user)
        assert t.version == 1
        assert t.is_active

    def test_versioning(self, app, admin_user):
        t = self._create_template(app, admin_user)
        t2, _ = CleansingService.update_template(t.id, {
            'description': 'Updated',
        })
        assert t2.version == 2
        old = CleansingService.get_template(t.id)
        assert not old.is_active

    def test_version_history(self, app, admin_user):
        t = self._create_template(app, admin_user)
        CleansingService.update_template(t.id, {'description': 'v2'})
        versions = CleansingService.get_template_versions('Test')
        assert len(versions) == 2

    def test_csv_pipeline(self, app, admin_user):
        t = self._create_template(app, admin_user)
        csv = 'Name,Email\njohn doe,JOHN@TEST.COM\njane smith,jane@test.com\nmissing name,\nbob w,JOHN@TEST.COM\n'
        job, _ = CleansingService.create_job(t.id, csv, 'test.csv', created_by=1)
        job, _ = CleansingService.execute_job(job.id)
        assert job.status == 'completed'
        assert job.total_rows == 4
        assert job.clean_rows >= 1
        assert job.duplicate_rows >= 1
        assert job.flagged_rows >= 1

    def test_format_rules(self, app, admin_user):
        t = self._create_template(app, admin_user)
        csv = 'Name,Email\njohn doe,JOHN@TEST.COM\n'
        job, _ = CleansingService.create_job(t.id, csv, 't.csv', created_by=1)
        job, _ = CleansingService.execute_job(job.id)
        clean, _ = CleansingService.get_job_results(job)
        assert clean[0]['email'] == 'john@test.com'
        assert clean[0]['name'] == 'John Doe'

    def test_missing_value_default(self, app, admin_user):
        t, _ = CleansingService.create_template({
            'name': 'Defaults',
            'missing_value_rules': {'phone': {'action': 'default', 'value': '000'}},
        }, created_by=1)
        csv = 'name,phone\nAlice,555\nBob,\n'
        job, _ = CleansingService.create_job(t.id, csv, 't.csv', created_by=1)
        job, _ = CleansingService.execute_job(job.id)
        clean, _ = CleansingService.get_job_results(job)
        bob = [r for r in clean if r.get('name') == 'Bob'][0]
        assert bob['phone'] == '000'

    def test_fuzzy_dedup(self, app, admin_user):
        t, _ = CleansingService.create_template({
            'name': 'Fuzzy',
            'dedup_fields': ['name'],
            'dedup_threshold': 0.6,
            'format_rules': {'name': 'lowercase'},
        }, created_by=1)
        csv = 'name,email\njohn smith,j1@t.com\njohn smithe,j2@t.com\nalice jones,a@t.com\n'
        job, _ = CleansingService.create_job(t.id, csv, 'f.csv', created_by=1)
        job, _ = CleansingService.execute_job(job.id)
        assert job.duplicate_rows >= 1

    def test_deactivate_template(self, app, admin_user):
        t = self._create_template(app, admin_user)
        ok, _ = CleansingService.delete_template(t.id)
        assert ok
        templates = CleansingService.list_templates(active_only=True)
        assert len(templates) == 0

    def test_list_jobs(self, app, admin_user):
        t = self._create_template(app, admin_user)
        CleansingService.create_job(t.id, 'a,b\n1,2\n', 'x.csv', created_by=1)
        jobs = CleansingService.list_jobs()
        assert len(jobs) >= 1
