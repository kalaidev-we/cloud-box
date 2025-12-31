from flask import Flask, render_template
from flask_login import LoginManager, current_user
from models import db, User, File
import os
from werkzeug.security import generate_password_hash
from sqlalchemy import inspect, text

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'storage')
# Use persistent storage path for DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.config['UPLOAD_FOLDER'], 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

from auth import auth as auth_blueprint
app.register_blueprint(auth_blueprint)

from routes import main as main_blueprint
app.register_blueprint(main_blueprint)

from chat import chat_bp
app.register_blueprint(chat_bp)

from admin import admin_bp
app.register_blueprint(admin_bp)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_storage_usage():
    if current_user.is_authenticated:
        my_files = File.query.filter_by(owner_id=current_user.id, is_folder=False).all()
        used_bytes = sum(f.size for f in my_files)
        used_mb = round(used_bytes / (1024 * 1024), 2)
        limit_mb = getattr(current_user, 'storage_limit', 5120)
        percentage = round((used_mb / limit_mb) * 100, 1) if limit_mb > 0 else 100
        return dict(storage_used=used_mb, storage_limit=limit_mb, storage_percent=percentage)
    return dict(storage_used=0, storage_limit=5120, storage_percent=0)

# Removed app.route('/') to allow main.dashboard to handle it

def create_app():
    with app.app_context():
        db.create_all()
        
        # Schema Migration for Admin/Storage
        try:
            inspector = inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('user')]
            
            with db.engine.connect() as conn:
                transaction = conn.begin()
                try:
                    if 'is_admin' not in columns:
                        conn.execute(text('ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0'))
                    if 'storage_limit' not in columns:
                        conn.execute(text('ALTER TABLE user ADD COLUMN storage_limit INTEGER DEFAULT 5120'))
                    transaction.commit()
                except Exception as e:
                    transaction.rollback()
                    print(f"Migration error: {e}")
        except Exception as e:
            print(f"Inspector error (DB might not exist yet): {e}")

        # Create root storage dir if not exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
        # Create Default Admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin_user = User(username='admin', password_hash=generate_password_hash('admin'), is_admin=True, storage_limit=5120)
            db.session.add(admin_user)
            db.session.commit()
    return app

if __name__ == '__main__':
    create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)
