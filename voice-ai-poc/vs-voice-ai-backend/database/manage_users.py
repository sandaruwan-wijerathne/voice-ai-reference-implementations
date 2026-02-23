#!/usr/bin/env python3
"""
Utility script to manage users and API keys in the database.
"""
import sys
import secrets
from pathlib import Path

# Add parent directory to path so we can import database module
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import create_user, get_all_users, get_user_by_api_key


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(32)


def create_new_user(username: str, api_key: str = None) -> dict:
    """Create a new user with an API key."""
    if api_key is None:
        api_key = generate_api_key()
    
    success = create_user(username, api_key)
    if success:
        return {"username": username, "api_key": api_key, "status": "created"}
    else:
        return {"username": username, "status": "failed", "error": "User already exists"}


def list_users():
    """List all users (without API keys for security)."""
    users = get_all_users()
    print(f"\nTotal users: {len(users)}")
    print("-" * 60)
    for user in users:
        print(f"ID: {user['id']}, Username: {user['username']}, Created: {user['created_at']}")
    print("-" * 60)


def main():
    """Main CLI interface."""
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python database/manage_users.py create <email> [api_key]  - Create a new user")
        print("  python database/manage_users.py list                     - List all users")
        print("  python database/manage_users.py verify <api_key>            - Verify an API key")
        return
    
    command = sys.argv[1].lower()
    
    if command == "create":
        if len(sys.argv) < 3:
            print("Error: Username (email) is required")
            return
        
        username = sys.argv[2]
        api_key = sys.argv[3] if len(sys.argv) > 3 else None
        
        result = create_new_user(username, api_key)
        if result["status"] == "created":
            print(f"\n✓ User created successfully!")
            print(f"  Username: {result['username']}")
            print(f"  API Key: {result['api_key']}")
            print(f"\n⚠️  Save this API key securely - it cannot be retrieved later!")
        else:
            print(f"\n✗ Failed to create user: {result.get('error', 'Unknown error')}")
    
    elif command == "list":
        list_users()
    
    elif command == "verify":
        if len(sys.argv) < 3:
            print("Error: API key is required")
            return
        
        api_key = sys.argv[2]
        user = get_user_by_api_key(api_key)
        if user:
            print(f"\n✓ Valid API key")
            print(f"  Username: {user['username']}")
            print(f"  User ID: {user['id']}")
        else:
            print("\n✗ Invalid API key")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
