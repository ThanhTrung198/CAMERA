"""
Authentication utilities and decorators
"""
from flask import session, jsonify
from functools import wraps


def login_required(f):
    """
    Decorator to require login for a route
    
    Usage:
        @app.route('/protected')
        @login_required
        def protected_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"error": "Unauthorized", "message": "Please login first"}), 401
        return f(*args, **kwargs)
    return decorated_function


def check_admin(f):
    """
    Decorator to require admin role
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        from config.settings import USERS
        user = USERS.get(session['user'])
        
        if not user or user.get('role') != 'admin':
            return jsonify({"error": "Forbidden", "message": "Admin access required"}), 403
        
        return f(*args, **kwargs)
    return decorated_function
