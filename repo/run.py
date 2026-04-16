import os
from app import create_app

config_name = os.environ.get('FLASK_CONFIG', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    os.makedirs('instance', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=app.config.get('DEBUG', False))
