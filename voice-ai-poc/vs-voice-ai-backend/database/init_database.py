#!/usr/bin/env python3
"""
CLI script to initialize the database.

This script creates the necessary database tables if they don't exist.
It can be run from the command line to set up the database.

Usage:
    python -m database.init_database
    python database/init_database.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import database
from database import init_database, get_db_connection


def main():
    """Main entry point for the database initialization script."""
    parser = argparse.ArgumentParser(
        description="Initialize the voice AI database and create necessary tables."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all existing tables before creating new ones (WARNING: This will delete all data!)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if database exists and tables are created without modifying anything",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help=f"Custom database path (default: {database.DB_PATH})",
    )
    
    args = parser.parse_args()
    
    if args.db_path:
        database.DB_PATH = Path(args.db_path)
        print(f"Using custom database path: {args.db_path}")
    
    db_path = database.DB_PATH
    
    if args.check:
        print(f"Checking database at: {db_path}")
        if not db_path.exists():
            print("Database file does not exist.")
            sys.exit(1)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name IN ('users', 'conversations', 'message_exchanges')
                """)
                tables = [row[0] for row in cursor.fetchall()]
                
                expected_tables = {'users', 'conversations', 'message_exchanges'}
                existing_tables = set(tables)
                
                if existing_tables == expected_tables:
                    print("All required tables exist:")
                    for table in sorted(existing_tables):
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        print(f"   - {table}: {count} rows")
                    sys.exit(0)
                else:
                    missing = expected_tables - existing_tables
                    print(f"Missing tables: {', '.join(missing)}")
                    sys.exit(1)
        except Exception as e:
            print(f"Error checking database: {e}")
            sys.exit(1)
    
    if args.reset:
        print(f"RESET MODE: This will delete all data in {db_path}")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted.")
            sys.exit(0)
        
        print(f"Dropping existing tables in {db_path}...")
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TABLE IF EXISTS message_exchanges")
                cursor.execute("DROP TABLE IF EXISTS conversations")
                cursor.execute("DROP TABLE IF EXISTS users")
                conn.commit()
            print("Existing tables dropped.")
        except Exception as e:
            print(f"Error dropping tables: {e}")
            sys.exit(1)
    
    print(f"Initializing database at: {db_path}")
    try:
        init_database()
        print("Database initialized successfully!")
        print(f"   Database location: {db_path}")
        print("   Created tables:")
        print("     - users")
        print("     - conversations")
        print("     - message_exchanges")
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
