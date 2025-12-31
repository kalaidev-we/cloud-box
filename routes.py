from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, File, Permission, User
import os
import uuid

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/dashboard')
@main.route('/dashboard/<int:folder_id>')
@login_required
def dashboard(folder_id=None):
    current_folder = None
    if folder_id:
        current_folder = File.query.get_or_404(folder_id)
        if not check_access(current_folder, current_user):
            flash('Permission denied', 'danger')
            return redirect(url_for('main.dashboard'))

    if folder_id:
        files = File.query.filter_by(parent_id=folder_id).all()
        shared_files = [] # In subfolders, everything is mixed in the list, but we could highlight shared ones if we query perms.
    else:
        # Root View: Owned files (root)
        files = File.query.filter_by(owner_id=current_user.id, parent_id=None).all()
        
        # Get files/folders shared directly with me
        shared_permissions = Permission.query.filter_by(user_id=current_user.id).all()
        shared_files = [p.file for p in shared_permissions]

    # Get list of other users for sharing dropdown
    other_users = User.query.filter(User.id != current_user.id).all()

    breadcrumbs = []
    curr = current_folder
    while curr:
        breadcrumbs.insert(0, curr)
        curr = curr.parent

    return render_template('dashboard.html', files=files, shared_files=shared_files, current_folder=current_folder, breadcrumbs=breadcrumbs, users=other_users)

def check_access(file_record, user):
    if file_record.owner_id == user.id:
        return True
    perm = Permission.query.filter_by(file_id=file_record.id, user_id=user.id).first()
    if perm:
        return True
    if file_record.parent_id:
        parent = File.query.get(file_record.parent_id)
        if parent:
            return check_access(parent, user)
    return False

def get_user_role(file_record, user):
    if file_record.owner_id == user.id:
        return 'owner'
    perm = Permission.query.filter_by(file_id=file_record.id, user_id=user.id).first()
    if perm:
        return perm.role
    if file_record.parent_id:
        parent = File.query.get(file_record.parent_id)
        if parent:
            return get_user_role(parent, user)
    return None

def scan_file(file_storage):
    """
    Simulate ClamAV scanning. 
    In prod, this would connect to clamd via socket.
    For MVP, we check for EICAR test or simple extensions.
    """
    if file_storage.filename.lower().endswith('.exe') or 'virus' in file_storage.filename.lower():
        return False, "Potential malware detected (Extension/Name blocked)"
    return True, "Clean"

@main.route('/analytics')
@login_required
def analytics():
    my_files = File.query.filter_by(owner_id=current_user.id, is_folder=False).all()
    my_usage = sum(f.size for f in my_files)
    my_file_count = len(my_files)
    largest_file_size = max([f.size for f in my_files]) if my_files else 0
    largest_files = sorted(my_files, key=lambda x: x.size, reverse=True)[:5]
    
    users = User.query.all()
    user_stats = []
    for u in users:
        u_files = File.query.filter_by(owner_id=u.id, is_folder=False).all()
        u_size = sum(f.size for f in u_files)
        u_count = len(u_files)
        user_stats.append({
            'username': u.username,
            'total_size': u_size,
            'file_count': u_count
        })
        
    return render_template('analytics.html', 
                           my_usage=my_usage, 
                           my_file_count=my_file_count, 
                           largest_file_size=largest_file_size,
                           largest_files=largest_files,
                           user_stats=user_stats)

@main.route('/share_file', methods=['POST'])
@login_required
def share_file():
    file_id = request.form.get('file_id')
    username = request.form.get('username')
    role = request.form.get('role')
    
    file_to_share = File.query.get_or_404(file_id)
    
    if file_to_share.owner_id != current_user.id:
        flash('Only owner can share', 'danger')
        return redirect(url_for('main.dashboard', folder_id=file_to_share.parent_id))
        
    user_to_share_with = User.query.filter_by(username=username).first()
    if not user_to_share_with:
        flash('User not found', 'warning')
        return redirect(url_for('main.dashboard', folder_id=file_to_share.parent_id))
        
    if user_to_share_with.id == current_user.id:
        flash('Cannot share with yourself', 'warning')
        return redirect(url_for('main.dashboard', folder_id=file_to_share.parent_id))
        
    existing_perm = Permission.query.filter_by(file_id=file_to_share.id, user_id=user_to_share_with.id).first()
    if existing_perm:
        existing_perm.role = role
        flash(f'Updated permissions for {username}', 'success')
    else:
        new_perm = Permission(file_id=file_to_share.id, user_id=user_to_share_with.id, role=role)
        db.session.add(new_perm)
        flash(f'Shared with {username}', 'success')
        
    db.session.commit()
    return redirect(url_for('main.dashboard', folder_id=file_to_share.parent_id))

@main.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id')
    parent_id = int(parent_id) if parent_id and parent_id != 'None' else None
    
    if parent_id:
        parent = File.query.get_or_404(parent_id)
        role = get_user_role(parent, current_user)
        if role not in ['owner', 'editor']:
            flash('Permission denied (Read Only)', 'danger')
            return redirect(url_for('main.dashboard', folder_id=parent_id))
    
    if not name:
        flash('Folder name required', 'warning')
        return redirect(url_for('main.dashboard', folder_id=parent_id))
        
    new_folder = File(name=name, is_folder=True, parent_id=parent_id, owner_id=current_user.id)
    db.session.add(new_folder)
    db.session.commit()
    flash('Folder created', 'success')
    return redirect(url_for('main.dashboard', folder_id=parent_id))

@main.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'warning')
        return redirect(request.url)
        
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'warning')
        return redirect(request.url)
        
    parent_id = request.form.get('parent_id')
    parent_id = int(parent_id) if parent_id and parent_id != 'None' else None

    if parent_id:
        parent = File.query.get_or_404(parent_id)
        role = get_user_role(parent, current_user)
        if role not in ['owner', 'editor']:
            flash('Permission denied (Read Only)', 'danger')
            return redirect(url_for('main.dashboard', folder_id=parent_id))

    if file:
        # Virus Scan
        is_clean, message = scan_file(file)
        if not is_clean:
            flash(message, 'danger')
            return redirect(url_for('main.dashboard', folder_id=parent_id))

        filename = secure_filename(file.filename)
        unique_filename = str(uuid.uuid4()) + "_" + filename
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        
        file.save(file_path)
        
        new_file = File(
            name=filename, is_folder=False, parent_id=parent_id,
            owner_id=current_user.id, path=unique_filename,
            size=os.path.getsize(file_path)
        )
        db.session.add(new_file)
        db.session.commit()
        flash('File uploaded successfully', 'success')
        
    return redirect(url_for('main.dashboard', folder_id=parent_id))

@main.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    file_record = File.query.get_or_404(file_id)
    if not check_access(file_record, current_user):
        flash('Permission denied', 'danger')
        return redirect(url_for('main.dashboard'))
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], file_record.path, download_name=file_record.name)

@main.route('/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    file_record = File.query.get_or_404(file_id)
    role = get_user_role(file_record, current_user)
    if role not in ['owner', 'editor']:
         flash('Permission denied', 'danger')
         return redirect(url_for('main.dashboard'))
             
    if not file_record.is_folder:
        try:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_record.path)
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
            
    db.session.delete(file_record)
    db.session.commit()
    flash('Item deleted', 'success')
    flash('Item deleted', 'success')
    return redirect(url_for('main.dashboard', folder_id=file_record.parent_id))



@main.route('/friends')
@login_required
def friends():
    users = User.query.filter(User.id != current_user.id).all()
    my_files = File.query.filter_by(owner_id=current_user.id, is_folder=False).all()
    return render_template('friends.html', users=users, my_files=my_files)

@main.route('/share_file', methods=['POST'])
@login_required
def share_file():
    username = request.form.get('username')
    file_id = request.form.get('file_id')
    role = request.form.get('role', 'viewer')
    
    if not username or not file_id:
        flash('Missing information', 'warning')
        return redirect(url_for('main.friends'))
        
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('main.friends'))
        
    file = File.query.get_or_404(file_id)
    if file.owner_id != current_user.id:
        flash('Permission denied', 'danger')
        return redirect(url_for('main.friends'))
        
    # Check if permission already exists
    existing_perm = Permission.query.filter_by(file_id=file.id, user_id=user.id).first()
    if existing_perm:
        existing_perm.role = role
        flash(f'Updated permission for {user.username}', 'success')
    else:
        perm = Permission(file_id=file.id, user_id=user.id, role=role)
        db.session.add(perm)
        flash(f'Shared {file.name} with {user.username}', 'success')
        
    db.session.commit()
    return redirect(url_for('main.friends'))
