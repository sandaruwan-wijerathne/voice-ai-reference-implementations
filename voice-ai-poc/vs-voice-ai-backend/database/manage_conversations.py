#!/usr/bin/env python3
"""
Utility script to manage conversations and message exchanges in the database.
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import database module
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import (
    get_all_conversations,
    get_conversation_by_id,
    get_message_exchanges_by_conversation_id,
)


def list_conversations():
    """List all conversations."""
    conversations = get_all_conversations()
    print(f"\nTotal conversations: {len(conversations)}")
    print("=" * 100)
    print(f"{'ID':<6} {'User ID':<8} {'Username':<30} {'Start Time':<25} {'End Time':<25} {'Rating':<8} {'Appt Booked':<12}")
    print("-" * 100)
    
    for conv in conversations:
        conv_id = conv.get('id', 'N/A')
        user_id = conv.get('user_id', 'N/A')
        username = conv.get('username', 'N/A') or 'N/A'
        start_time = conv.get('start_time', 'N/A') or 'N/A'
        end_time = conv.get('end_time', 'N/A') or 'N/A'
        rating = conv.get('rating', 'N/A') if conv.get('rating') is not None else 'N/A'
        appointment_booked = 'Yes' if conv.get('appointment_booked', 0) == 1 else 'No'
        
        # Truncate long usernames and timestamps for display
        username = username[:28] + '..' if len(username) > 30 else username
        start_time = start_time[:23] if len(start_time) > 25 else start_time
        end_time = end_time[:23] if len(end_time) > 25 else end_time
        
        print(f"{conv_id:<6} {user_id:<8} {username:<30} {start_time:<25} {end_time:<25} {rating:<8} {appointment_booked:<12}")
    
    print("=" * 100)


def list_message_exchanges(conversation_id: int):
    """List all message exchanges for a specific conversation."""
    # First verify the conversation exists
    conversation = get_conversation_by_id(conversation_id)
    if not conversation:
        print(f"\n✗ Conversation with ID {conversation_id} not found")
        return
    
    exchanges = get_message_exchanges_by_conversation_id(conversation_id)
    
    print(f"\nConversation ID: {conversation_id}")
    print(f"User ID: {conversation.get('user_id', 'N/A')}")
    print(f"Start Time: {conversation.get('start_time', 'N/A')}")
    print(f"End Time: {conversation.get('end_time', 'N/A') or 'Ongoing'}")
    print(f"Rating: {conversation.get('rating', 'N/A') if conversation.get('rating') is not None else 'N/A'}")
    print(f"Appointment Booked: {'Yes' if conversation.get('appointment_booked', 0) == 1 else 'No'}")
    print(f"\nTotal message exchanges: {len(exchanges)}")
    print("=" * 120)
    
    if not exchanges:
        print("No message exchanges found for this conversation.")
        print("=" * 120)
        return
    
    for idx, exchange in enumerate(exchanges, 1):
        print(f"\n--- Exchange #{idx} ---")
        print(f"ID: {exchange.get('id', 'N/A')}")
        print(f"Timestamp: {exchange.get('timestamp', 'N/A')}")
        print(f"User Input: {exchange.get('user_input', 'N/A') or '(empty)'}")
        print(f"AI Response: {exchange.get('ai_response', 'N/A') or '(empty)'}")
        print(f"Tokens - Input: {exchange.get('input_tokens', 'N/A') or 'N/A'}, "
              f"Output: {exchange.get('output_tokens', 'N/A') or 'N/A'}, "
              f"Total: {exchange.get('total_tokens', 'N/A') or 'N/A'}")
        print("-" * 120)
    
    print("=" * 120)


def show_conversation_details(conversation_id: int):
    """Show detailed information about a specific conversation."""
    conversation = get_conversation_by_id(conversation_id)
    if not conversation:
        print(f"\n✗ Conversation with ID {conversation_id} not found")
        return
    
    print(f"\n{'=' * 80}")
    print(f"Conversation Details")
    print(f"{'=' * 80}")
    print(f"ID: {conversation.get('id', 'N/A')}")
    print(f"User ID: {conversation.get('user_id', 'N/A')}")
    print(f"Start Time: {conversation.get('start_time', 'N/A')}")
    print(f"End Time: {conversation.get('end_time', 'N/A') or 'Ongoing'}")
    print(f"Rating: {conversation.get('rating', 'N/A') if conversation.get('rating') is not None else 'Not rated'}")
    print(f"Appointment Booked: {'Yes' if conversation.get('appointment_booked', 0) == 1 else 'No'}")
    print(f"{'=' * 80}")


def main():
    """Main CLI interface."""
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python database/manage_conversations.py list                                    - List all conversations")
        print("  python database/manage_conversations.py show <conversation_id>                   - Show conversation details")
        print("  python database/manage_conversations.py messages <conversation_id>             - List message exchanges for a conversation")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_conversations()
    
    elif command == "show":
        if len(sys.argv) < 3:
            print("Error: Conversation ID is required")
            print("Usage: python database/manage_conversations.py show <conversation_id>")
            return
        
        try:
            conversation_id = int(sys.argv[2])
            show_conversation_details(conversation_id)
        except ValueError:
            print("Error: Conversation ID must be a number")
    
    elif command == "messages":
        if len(sys.argv) < 3:
            print("Error: Conversation ID is required")
            print("Usage: python database/manage_conversations.py messages <conversation_id>")
            return
        
        try:
            conversation_id = int(sys.argv[2])
            list_message_exchanges(conversation_id)
        except ValueError:
            print("Error: Conversation ID must be a number")
    
    else:
        print(f"Unknown command: {command}")
        print("\nAvailable commands:")
        print("  list                                    - List all conversations")
        print("  show <conversation_id>                  - Show conversation details")
        print("  messages <conversation_id>               - List message exchanges for a conversation")


if __name__ == "__main__":
    main()
