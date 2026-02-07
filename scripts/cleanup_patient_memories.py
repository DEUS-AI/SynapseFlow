#!/usr/bin/env python3
"""
Cleanup script for patient memories.

This script:
1. Lists all Qdrant collections (shows both old shared and new isolated)
2. Shows memory counts per collection
3. Optionally deletes the old shared collection
4. Optionally clears specific patient collections

Usage:
    # Show current state
    python scripts/cleanup_patient_memories.py --status

    # Delete old shared collection
    python scripts/cleanup_patient_memories.py --delete-shared

    # Delete all patient collections (fresh start)
    python scripts/cleanup_patient_memories.py --delete-all

    # Delete specific patient's collection
    python scripts/cleanup_patient_memories.py --delete-patient patient:pablo
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

load_dotenv()


def get_qdrant_client():
    """Get Qdrant client."""
    from qdrant_client import QdrantClient

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    return QdrantClient(url=qdrant_url)


def show_status():
    """Show current state of all Qdrant collections."""
    print("\n" + "=" * 60)
    print("QDRANT COLLECTIONS STATUS")
    print("=" * 60)

    client = get_qdrant_client()
    collections = client.get_collections().collections

    if not collections:
        print("\nNo collections found in Qdrant.")
        return

    print(f"\nFound {len(collections)} collection(s):\n")

    shared_collections = []
    patient_collections = []

    for collection in collections:
        name = collection.name
        try:
            info = client.get_collection(name)
            count = info.points_count
        except Exception as e:
            count = f"Error: {e}"

        if name == "patient_memories":
            shared_collections.append((name, count))
            print(f"  ⚠️  SHARED: {name}")
            print(f"      Points: {count}")
            print(f"      WARNING: This is the old shared collection that can leak data!")
        elif name.startswith("patient_mem_"):
            patient_collections.append((name, count))
            patient_id = name.replace("patient_mem_", "").replace("_", ":")
            print(f"  ✅ ISOLATED: {name}")
            print(f"      Patient ID: {patient_id}")
            print(f"      Points: {count}")
        else:
            print(f"  📦 OTHER: {name}")
            print(f"      Points: {count}")
        print()

    print("-" * 60)
    print("SUMMARY:")
    print(f"  Shared collections (risk!): {len(shared_collections)}")
    print(f"  Isolated patient collections: {len(patient_collections)}")

    if shared_collections:
        print("\n⚠️  RECOMMENDATION: Delete the shared 'patient_memories' collection")
        print("   Run: python scripts/cleanup_patient_memories.py --delete-shared")


def delete_shared_collection():
    """Delete the old shared patient_memories collection."""
    print("\n" + "=" * 60)
    print("DELETING SHARED COLLECTION")
    print("=" * 60)

    client = get_qdrant_client()

    try:
        client.delete_collection("patient_memories")
        print("\n✅ Deleted 'patient_memories' collection")
        print("   All old potentially leaked data has been removed.")
    except Exception as e:
        print(f"\n❌ Error deleting collection: {e}")
        print("   (Collection may not exist)")


def delete_patient_collection(patient_id: str):
    """Delete a specific patient's isolated collection."""
    import re

    # Convert patient_id to collection name
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', patient_id)
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')
    collection_name = f"patient_mem_{safe_name}"

    print(f"\nDeleting collection for {patient_id}...")
    print(f"Collection name: {collection_name}")

    client = get_qdrant_client()

    try:
        client.delete_collection(collection_name)
        print(f"✅ Deleted '{collection_name}'")
    except Exception as e:
        print(f"❌ Error: {e}")


def delete_all_collections():
    """Delete ALL patient-related collections (fresh start)."""
    print("\n" + "=" * 60)
    print("DELETING ALL PATIENT COLLECTIONS")
    print("=" * 60)

    client = get_qdrant_client()
    collections = client.get_collections().collections

    deleted = 0
    for collection in collections:
        name = collection.name
        if name == "patient_memories" or name.startswith("patient_mem_"):
            try:
                client.delete_collection(name)
                print(f"  ✅ Deleted: {name}")
                deleted += 1
            except Exception as e:
                print(f"  ❌ Error deleting {name}: {e}")

    print(f"\n✅ Deleted {deleted} collection(s)")
    print("   Ready for fresh start with isolated collections.")


def main():
    parser = argparse.ArgumentParser(description="Manage patient memory collections in Qdrant")
    parser.add_argument("--status", action="store_true", help="Show current status of all collections")
    parser.add_argument("--delete-shared", action="store_true", help="Delete the old shared collection")
    parser.add_argument("--delete-all", action="store_true", help="Delete ALL patient collections (fresh start)")
    parser.add_argument("--delete-patient", type=str, help="Delete a specific patient's collection")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.delete_shared:
        confirm = input("This will delete the shared 'patient_memories' collection. Continue? [y/N]: ")
        if confirm.lower() == 'y':
            delete_shared_collection()
            show_status()
        else:
            print("Cancelled.")
    elif args.delete_all:
        confirm = input("This will delete ALL patient collections. Continue? [y/N]: ")
        if confirm.lower() == 'y':
            delete_all_collections()
            show_status()
        else:
            print("Cancelled.")
    elif args.delete_patient:
        confirm = input(f"This will delete collection for '{args.delete_patient}'. Continue? [y/N]: ")
        if confirm.lower() == 'y':
            delete_patient_collection(args.delete_patient)
            show_status()
        else:
            print("Cancelled.")
    else:
        # Default: show status
        show_status()
        print("\nUse --help for cleanup options.")


if __name__ == "__main__":
    main()
