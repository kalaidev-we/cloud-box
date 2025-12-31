from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Message
from datetime import datetime
from sqlalchemy import or_

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat')
@login_required
def chat_view():
    return render_template('chat.html')

@chat_bp.route('/chat/api/users')
@login_required
def get_users():
    users = User.query.filter(User.id != current_user.id).all()
    users_data = []
    for user in users:
        # Check for unread messages
        unread_count = Message.query.filter_by(sender_id=user.id, recipient_id=current_user.id, read=False).count()
        users_data.append({
            'id': user.id,
            'username': user.username,
            'unread': unread_count
        })
    return jsonify(users_data)

@chat_bp.route('/chat/api/messages/<int:user_id>')
@login_required
def get_messages(user_id):
    # Fetch messages between current user and selected user
    messages = Message.query.filter(
        or_(
            (Message.sender_id == current_user.id) & (Message.recipient_id == user_id),
            (Message.sender_id == user_id) & (Message.recipient_id == current_user.id)
        )
    ).order_by(Message.timestamp).all()
    
    # Mark received messages as read
    unread_messages = Message.query.filter_by(sender_id=user_id, recipient_id=current_user.id, read=False).all()
    for msg in unread_messages:
        msg.read = True
    if unread_messages:
        db.session.commit()
    
    msgs_data = []
    for msg in messages:
        msgs_data.append({
            'sender_id': msg.sender_id,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'is_me': msg.sender_id == current_user.id
        })
        
    return jsonify(msgs_data)

@chat_bp.route('/chat/api/send', methods=['POST'])
@login_required
def send_message():
    data = request.json
    recipient_id = data.get('recipient_id')
    content = data.get('content')
    
    if not recipient_id or not content:
        return jsonify({'error': 'Missing data'}), 400
        
    new_msg = Message(sender_id=current_user.id, recipient_id=recipient_id, content=content)
    db.session.add(new_msg)
    db.session.commit()
    
    return jsonify({'status': 'sent', 'timestamp': new_msg.timestamp.strftime('%H:%M')})
