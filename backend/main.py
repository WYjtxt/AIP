"""Production WSGI entry; app creation and jobs live in separate modules."""
from server_app_factory import create_app

app = create_app()
scheduler = app.apscheduler
globals().update(app.extensions['platform_jobs'])

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
