from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    files = db.relationship('File', backref='owner', lazy=True)
    permissions = db.relationship('Permission', backref='user', lazy=True)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    is_folder = db.Column(db.Boolean, default=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('file.id'), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    path = db.Column(db.String(512), nullable=True) # Physical path for files
    size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship for folders
    children = db.relationship('File', backref=db.backref('parent', remote_side=[id]), lazy=True)
    permissions = db.relationship('Permission', backref='file', lazy=True, cascade="all, delete-orphan")

class Permission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'owner', 'editor', 'viewer'
