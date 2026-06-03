import os
from enterprise_app import create_app, celery
from config import Config

app = create_app(Config)
celery.conf.update(app.config)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    app.run(host='0.0.0.0', port=port, debug=False)