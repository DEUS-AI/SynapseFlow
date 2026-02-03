#!/usr/bin/env python3
"""
Quick Demo of Improved Reasoning

Shows a single query with full reasoning trail output.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).parent / "src"))

from application.services.intelligent_chat_service import IntelligentChatService

load_dotenv()


async def main():
    """Demo improved reasoning."""
    print("\n" + "="*70)
    print("  Neurosymbolic Reasoning Demo")
    print("="*70)

    # Initialize
    chat = IntelligentChatService(openai_api_key=os.getenv("OPENAI_API_KEY"))

    # Test query with treatment recommendation (should trigger warning)
    question = "Should I take Infliximab for Crohn's disease?"

    print(f"\n📝 Question: {question}\n")

    response = await chat.query(question)

    print("🤖 Answer:")
    print("-" * 70)
    print(response.answer)
    print("-" * 70)

    print(f"\n🎯 Confidence: {response.confidence:.2f} ", end="")
    if response.confidence >= 0.8:
        print("(HIGH) ⭐⭐⭐")
    elif response.confidence >= 0.6:
        print("(MEDIUM) ⭐⭐")
    else:
        print("(LOW) ⭐")

    print(f"\n🧠 Reasoning Trail ({len(response.reasoning_trail)} steps):")
    for step in response.reasoning_trail:
        print(f"  {step}")

    print(f"\n📚 Sources ({len(response.sources)}):")
    for source in response.sources[:5]:
        print(f"  - {source.get('type')}: {source.get('name')}")

    print(f"\n💡 Related Concepts:")
    for concept in response.related_concepts[:5]:
        print(f"  - {concept}")

    print(f"\n⏱️  Query Time: {response.query_time_seconds:.2f}s")

    print("\n" + "="*70)
    print("✅ Neurosymbolic reasoning working successfully!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
