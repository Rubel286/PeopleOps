import os
from enterprise_app import create_app, celery
from config import Config

app = create_app(Config)
celery.conf.update(app.config)
if __name__ == '__main__':
    app.run(debug=True, port=5000)