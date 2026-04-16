"""Seed database with default roles and admin user."""
import os

from app import create_app
from app.extensions import db
from app.models.user import Role, User
from app.services.auth_service import AuthService


def seed():
    config_name = os.environ.get('FLASK_CONFIG', 'development')
    app = create_app(config_name)
    with app.app_context():
        # Create roles
        roles = ['admin', 'manager', 'operator', 'viewer']
        for role_name in roles:
            if not Role.query.filter_by(name=role_name).first():
                db.session.add(Role(name=role_name, description=f'{role_name.title()} role'))

        db.session.commit()

        # Create default admin
        if not User.query.filter_by(username='admin').first():
            admin_role = Role.query.filter_by(name='admin').first()
            AuthService.create_user(
                username='admin',
                email='admin@fieldservice.local',
                password='admin123',
                role='admin',
            )
            admin = User.query.filter_by(username='admin').first()
            admin.role_id = admin_role.id
            db.session.commit()
            print('Created admin user (admin / admin123)')

        # Create test users
        test_users = [
            ('manager1', 'manager1@fieldservice.local', 'pass123', 'manager'),
            ('operator1', 'operator1@fieldservice.local', 'pass123', 'operator'),
            ('viewer1', 'viewer1@fieldservice.local', 'pass123', 'viewer'),
        ]
        for username, email, password, role in test_users:
            if not User.query.filter_by(username=username).first():
                role_obj = Role.query.filter_by(name=role).first()
                AuthService.create_user(username, email, password, role)
                user = User.query.filter_by(username=username).first()
                user.role_id = role_obj.id
                db.session.commit()
                print(f'Created {role} user ({username} / {password})')

        print('Seed complete.')


if __name__ == '__main__':
    seed()
