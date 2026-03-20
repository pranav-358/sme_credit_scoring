import os, sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from extensions import db, login_manager, mail

load_dotenv()


def create_app():
    # Support both direct run and Vercel serverless
    BASE_DIR = os.path.normpath(os.path.join(BACKEND_DIR, '..'))
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, 'frontend', 'pages'),
        static_folder=os.path.join(BASE_DIR,   'frontend', 'assets'),
        static_url_path='/static'
    )

    # Fix for running behind Hugging Face reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # SECRET_KEY — fallback ensures sessions always work even without env var
    secret = os.environ.get('SECRET_KEY') or os.getenv('SECRET_KEY', 'SMECreditAI-fallback-key-2026-xyz')
    app.config['SECRET_KEY'] = secret
    app.config['SESSION_COOKIE_SECURE']   = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_NAME']     = 'smecreditai_session'
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours
    # Use PostgreSQL on Railway (DATABASE_URL set automatically),
    # fall back to SQLite locally
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Railway gives postgres:// but SQLAlchemy needs postgresql://
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    else:
        # Ensure instance folder exists for SQLite
        instance_dir = os.path.normpath(os.path.join(BACKEND_DIR, '..', 'instance'))
        os.makedirs(instance_dir, exist_ok=True)
        database_url = 'sqlite:///' + os.path.join(instance_dir, 'sme_credit.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Flask-Mail ─────────────────────────────────────────────────────────
    app.config['MAIL_SERVER']          = 'smtp.gmail.com'
    app.config['MAIL_PORT']            = 587
    app.config['MAIL_USE_TLS']         = True
    app.config['MAIL_USERNAME']        = os.getenv('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD']        = os.getenv('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER']  = os.getenv('MAIL_DEFAULT_SENDER',
                                                    os.getenv('MAIL_USERNAME', ''))

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    login_manager.login_view = 'auth.login'

    from routes.auth      import auth_bp
    from routes.main      import main_bp
    from routes.loan      import loan_bp
    from routes.score     import score_bp
    from routes.optimizer import optimizer_bp
    from routes.lender    import lender_bp
    from routes.report    import report_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(loan_bp)
    app.register_blueprint(score_bp)
    app.register_blueprint(optimizer_bp)
    app.register_blueprint(lender_bp)
    app.register_blueprint(report_bp)

    with app.app_context():
        from models.user             import User
        from models.loan_application import LoanApplication
        db.create_all()

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template('score_error.html', error=str(e)), 500

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)