from flask import Flask, render_template
from flask_login import LoginManager
from models import db, User
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-prod' # TODO: Use env var
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Removed app.route('/') to allow main.dashboard to handle it

def create_app():
    with app.app_context():
        db.create_all()
        # Create root storage dir if not exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
    return app

if __name__ == '__main__':
    create_app()
    app.run(host='0.0.0.0', port=5001, debug=True)
