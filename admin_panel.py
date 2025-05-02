#!/usr/bin/env python3
import os
import asyncio
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import aiosqlite
import asyncpg
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from config import ADMIN_ID, USE_POSTGRES, POSTGRES_DSN, DB_FILE

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'development_secret_key')

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, password_hash, is_admin=False):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = is_admin

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Get admin credentials from environment variables with fallbacks
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')

# Mock user database (for admin access)
users = {
    ADMIN_USERNAME: User(1, ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD), True)
}

@login_manager.user_loader
def load_user(user_id):
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    return users.get(admin_username) if int(user_id) == 1 else None

# Async database access
async def get_db():
    if USE_POSTGRES:
        try:
            conn = await asyncpg.connect(POSTGRES_DSN)
            return conn, True
        except Exception as e:
            print(f"Error connecting to PostgreSQL: {e}")
            print("Falling back to SQLite...")
            conn = await aiosqlite.connect(DB_FILE)
            return conn, False
    else:
        conn = await aiosqlite.connect(DB_FILE)
        return conn, False

# Route for login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users.get(username)
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Dashboard route
@app.route('/')
@login_required
def dashboard():
    try:
        stats = asyncio.run(get_stats())
        return render_template('dashboard.html', stats=stats)
    except Exception as e:
        print(f"Error loading dashboard: {e}")
        # Provide default stats in case of error
        default_stats = {
            "weekly_added": 0,
            "weekly_blacklisted": 0,
            "total_users": 0,
            "blacklisted_users": 0,
            "groups_count": 0
        }
        return render_template('dashboard.html', stats=default_stats)

# Health check route
@app.route('/health')
def health_check():
    return 'OK', 200

# Groups route
@app.route('/groups')
@login_required
def groups():
    try:
        groups_data = asyncio.run(get_groups())
        return render_template('groups.html', groups=groups_data)
    except Exception as e:
        print(f"Error loading groups: {e}")
        return render_template('groups.html', groups=[])

# Users route
@app.route('/users')
@login_required
def users_list():
    try:
        page = request.args.get('page', 1, type=int)
        users_data, total_pages = asyncio.run(get_users(page))
        return render_template('users.html', users=users_data, page=page, total_pages=total_pages)
    except Exception as e:
        print(f"Error loading users: {e}")
        return render_template('users.html', users=[], page=1, total_pages=1)

# Get statistics from database
async def get_stats():
    conn, is_postgres = await get_db()
    try:
        today = datetime.datetime.now()
        week_ago = today - datetime.timedelta(days=7)
        
        today_str = today.strftime("%Y-%m-%d")
        week_ago_str = week_ago.strftime("%Y-%m-%d")
        
        # Проверим существуют ли таблицы
        if is_postgres:
            try:
                # Для PostgreSQL сначала проверим существование таблицы stats
                table_exists = await conn.fetchval("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'stats')")
                if not table_exists:
                    # Таблицы нет, возвращаем нулевые значения
                    return {
                        "weekly_added": 0,
                        "weekly_blacklisted": 0,
                        "total_users": 0,
                        "blacklisted_users": 0,
                        "groups_count": 0
                    }
                
                # Для PostgreSQL используем строковые даты и сравниваем их напрямую
                weekly_stats = await conn.fetchrow(
                    "SELECT COALESCE(SUM(users_added), 0) as added, COALESCE(SUM(users_blacklisted), 0) as blacklisted FROM stats WHERE date BETWEEN $1 AND $2",
                    datetime.date.fromisoformat(week_ago_str), datetime.date.fromisoformat(today_str)
                )
                
                # Get total users count
                users_table_exists = await conn.fetchval("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
                if users_table_exists:
                    total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
                    blacklisted = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_blacklisted = TRUE")
                else:
                    total_users = 0
                    blacklisted = 0
                
                # Get source groups count
                groups_table_exists = await conn.fetchval("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'source_groups')")
                if groups_table_exists:
                    groups_count = await conn.fetchval("SELECT COUNT(*) FROM source_groups")
                else:
                    groups_count = 0
                
                return {
                    "weekly_added": weekly_stats['added'] if weekly_stats else 0,
                    "weekly_blacklisted": weekly_stats['blacklisted'] if weekly_stats else 0,
                    "total_users": total_users if total_users is not None else 0,
                    "blacklisted_users": blacklisted if blacklisted is not None else 0,
                    "groups_count": groups_count if groups_count is not None else 0
                }
            except Exception as e:
                print(f"PostgreSQL error: {e}")
                # В случае ошибки возвращаем нулевые значения
                return {
                    "weekly_added": 0,
                    "weekly_blacklisted": 0,
                    "total_users": 0,
                    "blacklisted_users": 0,
                    "groups_count": 0
                }
        else:
            # SQLite version
            try:
                # Проверим существование таблицы users
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stats'")
                table_exists = await cursor.fetchone()
                
                if not table_exists:
                    return {
                        "weekly_added": 0,
                        "weekly_blacklisted": 0,
                        "total_users": 0,
                        "blacklisted_users": 0,
                        "groups_count": 0
                    }
                
                cursor = await conn.execute(
                    "SELECT COALESCE(SUM(users_added), 0), COALESCE(SUM(users_blacklisted), 0) FROM stats WHERE date BETWEEN ? AND ?",
                    (week_ago_str, today_str)
                )
                weekly_stats = await cursor.fetchone()
                
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                users_table_exists = await cursor.fetchone()
                
                if users_table_exists:
                    cursor = await conn.execute("SELECT COUNT(*) FROM users")
                    total_users = await cursor.fetchone()
                    
                    cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE is_blacklisted = 1")
                    blacklisted = await cursor.fetchone()
                else:
                    total_users = (0,)
                    blacklisted = (0,)
                
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='source_groups'")
                groups_table_exists = await cursor.fetchone()
                
                if groups_table_exists:
                    cursor = await conn.execute("SELECT COUNT(*) FROM source_groups")
                    groups_count = await cursor.fetchone()
                else:
                    groups_count = (0,)
                
                return {
                    "weekly_added": weekly_stats[0] if weekly_stats else 0,
                    "weekly_blacklisted": weekly_stats[1] if weekly_stats else 0,
                    "total_users": total_users[0] if total_users else 0,
                    "blacklisted_users": blacklisted[0] if blacklisted else 0,
                    "groups_count": groups_count[0] if groups_count else 0
                }
            except Exception as e:
                print(f"SQLite error: {e}")
                return {
                    "weekly_added": 0,
                    "weekly_blacklisted": 0,
                    "total_users": 0,
                    "blacklisted_users": 0,
                    "groups_count": 0
                }
    except Exception as e:
        print(f"Error getting stats: {e}")
        # Return empty stats in case of error
        return {
            "weekly_added": 0,
            "weekly_blacklisted": 0,
            "total_users": 0,
            "blacklisted_users": 0,
            "groups_count": 0
        }
    finally:
        await conn.close()

# Get groups from database
async def get_groups():
    conn, is_postgres = await get_db()
    try:
        if is_postgres:
            groups = await conn.fetch("SELECT group_id, date_added FROM source_groups ORDER BY date_added DESC")
            return [{"group_id": group["group_id"], "date_added": group["date_added"]} for group in groups]
        else:
            cursor = await conn.execute("SELECT group_id, date_added FROM source_groups ORDER BY date_added DESC")
            groups = await cursor.fetchall()
            return [{"group_id": group[0], "date_added": group[1]} for group in groups]
    except Exception as e:
        print(f"Error getting groups: {e}")
        return []
    finally:
        await conn.close()

# Get users from database with pagination
async def get_users(page=1, per_page=20):
    conn, is_postgres = await get_db()
    try:
        offset = (page - 1) * per_page
        
        if is_postgres:
            # Get total count for pagination
            total = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_pages = (total + per_page - 1) // per_page
            
            # Get users with pagination
            users = await conn.fetch(
                "SELECT user_id, username, date_added, is_blacklisted FROM users ORDER BY date_added DESC LIMIT $1 OFFSET $2",
                per_page, offset
            )
            
            return [
                {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "date_added": user["date_added"],
                    "is_blacklisted": user["is_blacklisted"]
                } for user in users
            ], total_pages
        else:
            # Get total count for pagination
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            total = await cursor.fetchone()
            total = total[0] if total else 0
            total_pages = (total + per_page - 1) // per_page
            
            # Get users with pagination
            cursor = await conn.execute(
                "SELECT user_id, username, date_added, is_blacklisted FROM users ORDER BY date_added DESC LIMIT ? OFFSET ?",
                (per_page, offset)
            )
            users = await cursor.fetchall()
            
            return [
                {
                    "user_id": user[0],
                    "username": user[1],
                    "date_added": user[2],
                    "is_blacklisted": user[3]
                } for user in users
            ], total_pages
    except Exception as e:
        print(f"Error getting users: {e}")
        return [], 1
    finally:
        await conn.close()

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs(os.path.join(os.path.dirname(__file__), 'templates'), exist_ok=True)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Herman Admin Panel')
    parser.add_argument('--port', type=int, default=8080, help='Port to run the admin panel on')
    args = parser.parse_args()
    
    # Run app
    port = int(os.environ.get('PORT', args.port))
    print(f"Starting admin panel on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False) 