import aiosqlite
import asyncpg
import datetime
from config import DB_FILE, USE_POSTGRES, POSTGRES_DSN, SOURCE_GROUPS

class Database:
    def __init__(self):
        self.conn = None
        self.use_postgres = USE_POSTGRES
        
    @classmethod
    async def create(cls):
        """Factory method to properly create and initialize a Database instance asynchronously"""
        db = cls()
        
        # Connect to database (PostgreSQL or SQLite based on config)
        if db.use_postgres:
            try:
                # Create PostgreSQL connection
                db.conn = await asyncpg.connect(POSTGRES_DSN)
                print("Connected to PostgreSQL database")
            except Exception as e:
                print(f"Error connecting to PostgreSQL: {e}")
                print("Falling back to SQLite...")
                db.use_postgres = False
                db.conn = await aiosqlite.connect(DB_FILE)
        else:
            db.conn = await aiosqlite.connect(DB_FILE)
            print("Connected to SQLite database")
            
        await db._create_tables()
        await db._initialize_source_groups()
        return db
        
    async def _create_tables(self):
        if self.use_postgres:
            # PostgreSQL schema
            await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                date_added TIMESTAMP,
                is_blacklisted BOOLEAN DEFAULT FALSE
            )
            ''')
            
            await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                id SERIAL PRIMARY KEY,
                date DATE,
                users_added INTEGER DEFAULT 0,
                users_blacklisted INTEGER DEFAULT 0
            )
            ''')
            
            await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS source_groups (
                group_id BIGINT PRIMARY KEY,
                date_added TIMESTAMP
            )
            ''')
        else:
            # SQLite schema
            await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                date_added TEXT,
                is_blacklisted INTEGER DEFAULT 0
            )
            ''')
            
            await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                users_added INTEGER DEFAULT 0,
                users_blacklisted INTEGER DEFAULT 0
            )
            ''')
            
            await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS source_groups (
                group_id INTEGER PRIMARY KEY,
                date_added TEXT
            )
            ''')
            
            await self.conn.commit()
    
    async def _initialize_source_groups(self):
        """Add initial source groups from config if not already in the database"""
        for group_id in SOURCE_GROUPS:
            await self.add_source_group(group_id)
    
    async def add_source_group(self, group_id):
        """Add a group to the list of groups to monitor"""
        now = datetime.datetime.now()
        
        if self.use_postgres:
            # Check if group exists
            group = await self.conn.fetchrow(
                "SELECT group_id FROM source_groups WHERE group_id = $1", group_id
            )
            
            if not group:
                await self.conn.execute(
                    "INSERT INTO source_groups (group_id, date_added) VALUES ($1, $2)",
                    group_id, now
                )
                return True
        else:
            cursor = await self.conn.execute(
                "SELECT group_id FROM source_groups WHERE group_id = ?", (group_id,)
            )
            group = await cursor.fetchone()
            
            if not group:
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                await self.conn.execute(
                    "INSERT INTO source_groups (group_id, date_added) VALUES (?, ?)",
                    (group_id, now_str)
                )
                await self.conn.commit()
                return True
                
        return False
    
    async def get_source_groups(self):
        """Get all groups to monitor"""
        if self.use_postgres:
            groups = await self.conn.fetch("SELECT group_id FROM source_groups")
            return [group['group_id'] for group in groups]
        else:
            cursor = await self.conn.execute("SELECT group_id FROM source_groups")
            groups = await cursor.fetchall()
            return [group[0] for group in groups]
    
    async def add_user(self, user_id, username=None):
        """Add a user to the database"""
        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        if self.use_postgres:
            # Check if user exists
            user = await self.conn.fetchrow(
                "SELECT user_id FROM users WHERE user_id = $1", user_id
            )
            
            if not user:
                # Insert user
                await self.conn.execute(
                    "INSERT INTO users (user_id, username, date_added) VALUES ($1, $2, $3)",
                    user_id, username, now
                )
                
                # Update stats for today
                stats = await self.conn.fetchrow(
                    "SELECT id FROM stats WHERE date = $1", 
                    datetime.date.fromisoformat(today)
                )
                
                if stats:
                    await self.conn.execute(
                        "UPDATE stats SET users_added = users_added + 1 WHERE date = $1",
                        datetime.date.fromisoformat(today)
                    )
                else:
                    await self.conn.execute(
                        "INSERT INTO stats (date, users_added) VALUES ($1, 1)",
                        datetime.date.fromisoformat(today)
                    )
                
                return True
        else:
            # SQLite version
            cursor = await self.conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()
            
            if not user:
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                await self.conn.execute(
                    "INSERT INTO users (user_id, username, date_added) VALUES (?, ?, ?)",
                    (user_id, username, now_str)
                )
                
                # Update stats for today
                cursor = await self.conn.execute(
                    "SELECT id FROM stats WHERE date = ?", (today,)
                )
                stats = await cursor.fetchone()
                
                if stats:
                    await self.conn.execute(
                        "UPDATE stats SET users_added = users_added + 1 WHERE date = ?",
                        (today,)
                    )
                else:
                    await self.conn.execute(
                        "INSERT INTO stats (date, users_added) VALUES (?, 1)",
                        (today,)
                    )
                
                await self.conn.commit()
                return True
                
        return False
    
    async def blacklist_user(self, user_id):
        """Mark a user as blacklisted"""
        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        if self.use_postgres:
            # Check if user exists
            user = await self.conn.fetchrow(
                "SELECT user_id FROM users WHERE user_id = $1", user_id
            )
            
            if user:
                await self.conn.execute(
                    "UPDATE users SET is_blacklisted = TRUE WHERE user_id = $1",
                    user_id
                )
            else:
                await self.conn.execute(
                    "INSERT INTO users (user_id, date_added, is_blacklisted) VALUES ($1, $2, TRUE)",
                    user_id, now
                )
            
            # Update stats for today
            stats = await self.conn.fetchrow(
                "SELECT id FROM stats WHERE date = $1", 
                datetime.date.fromisoformat(today)
            )
            
            if stats:
                await self.conn.execute(
                    "UPDATE stats SET users_blacklisted = users_blacklisted + 1 WHERE date = $1",
                    datetime.date.fromisoformat(today)
                )
            else:
                await self.conn.execute(
                    "INSERT INTO stats (date, users_blacklisted) VALUES ($1, 1)",
                    datetime.date.fromisoformat(today)
                )
        else:
            # SQLite version
            cursor = await self.conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()
            
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            
            if user:
                await self.conn.execute(
                    "UPDATE users SET is_blacklisted = 1 WHERE user_id = ?",
                    (user_id,)
                )
            else:
                await self.conn.execute(
                    "INSERT INTO users (user_id, date_added, is_blacklisted) VALUES (?, ?, 1)",
                    (user_id, now_str)
                )
            
            # Update stats for today
            cursor = await self.conn.execute(
                "SELECT id FROM stats WHERE date = ?", (today,)
            )
            stats = await cursor.fetchone()
            
            if stats:
                await self.conn.execute(
                    "UPDATE stats SET users_blacklisted = users_blacklisted + 1 WHERE date = ?",
                    (today,)
                )
            else:
                await self.conn.execute(
                    "INSERT INTO stats (date, users_blacklisted) VALUES (?, 1)",
                    (today,)
                )
            
            await self.conn.commit()
            
        return True
    
    async def is_blacklisted(self, user_id):
        """Check if a user is blacklisted"""
        if self.use_postgres:
            user = await self.conn.fetchrow(
                "SELECT is_blacklisted FROM users WHERE user_id = $1", user_id
            )
            
            if user:
                return user['is_blacklisted']
        else:
            cursor = await self.conn.execute(
                "SELECT is_blacklisted FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()
            
            if user:
                return bool(user[0])
                
        return False
    
    async def get_weekly_stats(self):
        """Get stats for the last 7 days"""
        today = datetime.datetime.now()
        week_ago = today - datetime.timedelta(days=7)
        
        today_str = today.strftime("%Y-%m-%d")
        week_ago_str = week_ago.strftime("%Y-%m-%d")
        
        if self.use_postgres:
            stats = await self.conn.fetchrow(
                "SELECT SUM(users_added), SUM(users_blacklisted) FROM stats WHERE date BETWEEN $1 AND $2",
                datetime.date.fromisoformat(week_ago_str), datetime.date.fromisoformat(today_str)
            )
            
            return {
                "users_added": stats[0] if stats[0] else 0,
                "users_blacklisted": stats[1] if stats[1] else 0
            }
        else:
            cursor = await self.conn.execute(
                "SELECT SUM(users_added), SUM(users_blacklisted) FROM stats WHERE date BETWEEN ? AND ?",
                (week_ago_str, today_str)
            )
            
            stats = await cursor.fetchone()
            return {
                "users_added": stats[0] if stats[0] else 0,
                "users_blacklisted": stats[1] if stats[1] else 0
            }
    
    async def close(self):
        """Close database connection"""
        if self.use_postgres:
            await self.conn.close()
        else:
            await self.conn.close() 