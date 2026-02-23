import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent
DB_PATH = _project_root / "data" / "voice-ai.db"

# Export DB_PATH for use in backup scripts
__all__ = ['DB_PATH', 'init_database', 'get_db_connection', 'get_user_by_api_key', 
           'create_user', 'get_all_users', 'create_conversation', 'end_conversation',
           'update_conversation_rating', 'get_conversation_by_id', 'create_message_exchange',
           'get_all_conversations', 'get_message_exchanges_by_conversation_id']


def init_database():
    """Initialize the database and create the users and conversations tables if they don't exist."""
    # Ensure the data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                api_key TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                rating INTEGER,
                appointment_booked INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        # Create message_exchanges table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                user_input TEXT,
                ai_response TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_tokens INTEGER,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        conn.commit()


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    # Ensure the data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
    finally:
        conn.close()


def get_user_by_api_key(api_key: str) -> dict | None:
    """Get user by API key. Returns None if not found."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE api_key = ?", (api_key,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def create_user(username: str, api_key: str) -> bool:
    """Create a new user. Returns True if successful, False if user already exists."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, api_key) VALUES (?, ?)",
                (username, api_key)
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def get_all_users():
    """Get all users (for admin purposes)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, created_at FROM users")
        return [dict(row) for row in cursor.fetchall()]


def create_conversation(user_id: int) -> int:
    """
    Create a new conversation record when a conversation starts.
    
    Parameters:
        user_id (int): The ID of the user starting the conversation.
    
    Returns:
        int: The ID of the newly created conversation record.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        start_time = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT INTO conversations (user_id, start_time) VALUES (?, ?)",
            (user_id, start_time)
        )
        conn.commit()
        return cursor.lastrowid


def end_conversation(conversation_id: int, appointment_booked: bool = False) -> bool:
    """
    Update a conversation record when a conversation ends.
    
    Parameters:
        conversation_id (int): The ID of the conversation to update.
        appointment_booked (bool): Whether an appointment was successfully booked.
    
    Returns:
        bool: True if the conversation was updated successfully, False otherwise.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        end_time = datetime.utcnow().isoformat()
        appointment_booked_int = 1 if appointment_booked else 0
        cursor.execute(
            "UPDATE conversations SET end_time = ?, appointment_booked = ? WHERE id = ?",
            (end_time, appointment_booked_int, conversation_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def update_conversation_rating(conversation_id: int, rating: int) -> bool:
    """
    Update the rating for a conversation.
    
    Parameters:
        conversation_id (int): The ID of the conversation to update.
        rating (int): The rating value (typically 1-5).
    
    Returns:
        bool: True if the rating was updated successfully, False otherwise.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE conversations SET rating = ? WHERE id = ?",
            (rating, conversation_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_conversation_by_id(conversation_id: int) -> dict | None:
    """
    Get a conversation by its ID.
    
    Parameters:
        conversation_id (int): The ID of the conversation.
    
    Returns:
        dict | None: The conversation record as a dictionary, or None if not found.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def create_message_exchange(
    conversation_id: int,
    user_input: str | None = None,
    ai_response: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> int:
    """
    Create a new message exchange record.
    
    Parameters:
        conversation_id (int): The ID of the conversation this exchange belongs to.
        user_input (str | None): The user's input text.
        ai_response (str | None): The AI's response text.
        input_tokens (int | None): Number of input tokens used.
        output_tokens (int | None): Number of output tokens used.
        total_tokens (int | None): Total tokens used.
    
    Returns:
        int: The ID of the newly created message exchange record.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO message_exchanges 
               (conversation_id, timestamp, user_input, ai_response, input_tokens, output_tokens, total_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                conversation_id,
                timestamp,
                user_input,
                ai_response,
                input_tokens,
                output_tokens,
                total_tokens,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_all_conversations():
    """
    Get all conversations with user information.
    
    Returns:
        list: List of conversation records with user information.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.id,
                c.user_id,
                u.username,
                c.start_time,
                c.end_time,
                c.rating,
                c.appointment_booked
            FROM conversations c
            LEFT JOIN users u ON c.user_id = u.id
            ORDER BY c.start_time DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_message_exchanges_by_conversation_id(conversation_id: int):
    """
    Get all message exchanges for a specific conversation.
    
    Parameters:
        conversation_id (int): The ID of the conversation.
    
    Returns:
        list: List of message exchange records for the conversation.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM message_exchanges 
               WHERE conversation_id = ? 
               ORDER BY timestamp ASC""",
            (conversation_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
