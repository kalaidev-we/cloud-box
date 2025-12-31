from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from models import db, User, File
from functools import wraps
import os

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            flash('Admin access required', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin')
@login_required
@admin_required
def dashboard():
    users = User.query.all()
    total_users = len(users)
    
    # Calculate total storage across all users
    all_files = File.query.filter_by(is_folder=False).all()
    total_used_bytes = sum(f.size for f in all_files)
    total_used_mb = round(total_used_bytes / (1024 * 1024), 2)
    
    # Calculate global allocated space (Quota)
    total_allocated_mb = sum(getattr(u, 'storage_limit', 5120) for u in users)
    total_unused_allocated_mb = total_allocated_mb - total_used_mb
    
    # User stats for table
    users_data = []
    for user in users:
        u_files = File.query.filter_by(owner_id=user.id, is_folder=False).all()
        u_used_bytes = sum(f.size for f in u_files)
        u_used_mb = round(u_used_bytes / (1024 * 1024), 2)
        u_limit = getattr(user, 'storage_limit', 5120)
        u_percent = round((u_used_mb / u_limit) * 100, 1) if u_limit > 0 else 100
        
        users_data.append({
            'id': user.id,
            'username': user.username,
            'is_admin': getattr(user, 'is_admin', False),
            'used_mb': u_used_mb,
            'limit_mb': u_limit,
            'percent': u_percent
        })
        
    return render_template('admin.html', 
                           total_users=total_users, 
                           total_used_mb=total_used_mb,
                           total_allocated_mb=total_allocated_mb,
                           total_unused_mb=total_unused_allocated_mb,
                           users=users_data)

@admin_bp.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Cannot delete yourself', 'warning')
        return redirect(url_for('admin.dashboard'))
        
    user = User.query.get_or_404(user_id)
    
    # Delete physical files
    files = File.query.filter_by(owner_id=user.id, is_folder=False).all()
    for f in files:
        try:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f.path)
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception as e:
            print(f"Error deleting file {f.path}: {e}")
            
    # Database cascade should handle permissions/file records if set, but let's be safe
    # If cascade not set on relationships, we might need manual delete.
    # User model: relationships files, permissions. 
    # File model relationship permissions has cascade "all, delete-orphan".
    # User model files relationship doesn't have cascade specified in models.py snippet I saw.
    # It says: keys = db.relationship('File', backref='owner', lazy=True)
    # We should delete files manually from DB to be clean.
    File.query.filter_by(owner_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {user.username} deleted', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/update_limit/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def update_limit(user_id):
    user = User.query.get_or_404(user_id)
    new_limit = request.form.get('limit_mb')
    
    if new_limit:
        try:
            user.storage_limit = int(new_limit)
            db.session.commit()
            flash(f'Storage limit updated for {user.username}', 'success')
        except ValueError:
            flash('Invalid limit value', 'danger')
            
    return redirect(url_for('admin.dashboard'))
