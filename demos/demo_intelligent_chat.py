#!/usr/bin/env python3
"""
Intelligent Chat Demo - Neurosymbolic Medical Q&A

Interactive chat interface combining:
- Medical Knowledge Graph
- DDA Metadata Graph
- RAG-based document retrieval
- Neurosymbolic reasoning
- Validation and confidence scoring

Usage:
    python demos/demo_intelligent_chat.py

Commands:
    /help       - Show available commands
    /context    - Show knowledge graph statistics
    /sources    - Show sources from last answer
    /reasoning  - Show reasoning trail from last answer
    /confidence - Show confidence breakdown
    /reset      - Clear conversation history
    /quit       - Exit chat
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from application.services.intelligent_chat_service import IntelligentChatService, Message
from application.services.cross_graph_query_builder import CrossGraphQueryBuilder
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Set to WARNING to reduce noise in chat
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InteractiveChatDemo:
    """Interactive chat demo with command support."""

    def __init__(self):
        """Initialize the chat demo."""
        load_dotenv()

        print("=" * 70)
        print("  Intelligent Medical Chat - Neurosymbolic Q&A")
        print("=" * 70)
        print("\nInitializing services...")

        try:
            self.chat_service = IntelligentChatService()
            self.query_builder = CrossGraphQueryBuilder()
            print("✓ Chat service initialized")
        except Exception as e:
            print(f"\n✗ Initialization failed: {e}")
            raise

        self.conversation_history = []
        self.last_response = None

        print("\nType /help for available commands")
        print("Ask any question about medical concepts or data structures\n")

    def print_header(self, text: str):
        """Print a formatted header."""
        print("\n" + "-" * 70)
        print(f"  {text}")
        print("-" * 70)

    def show_help(self):
        """Show available commands."""
        self.print_header("Available Commands")
        print("""
/help       - Show this help message
/context    - Show knowledge graph statistics
/sources    - Show sources from last answer
/reasoning  - Show reasoning trail from last answer
/confidence - Show confidence breakdown for last answer
/reset      - Clear conversation history
/quit       - Exit chat

Just type your question to chat!

Example questions:
- What treatments are available for Crohn's Disease?
- Which data tables contain information about autoimmune diseases?
- What is the relationship between vitamin D and lupus?
- Show me columns related to patient treatments
""")

    async def show_context(self):
        """Show knowledge graph statistics."""
        self.print_header("Knowledge Graph Context")

        try:
            result = self.query_builder.get_cross_graph_statistics()

            if result.records:
                stats = result.records[0]
                print(f"""
Medical Entities:     {stats.get('medical_count', 0)}
Data Entities:        {stats.get('data_count', 0)}
SEMANTIC Links:       {stats.get('semantic_links', 0)}
Total Relationships:  {stats.get('total_relationships', 0)}
Total Entities:       {stats.get('total_entities', 0)}

This unified Neo4j graph enables intelligent queries across both
medical knowledge and data catalog metadata.
""")
        except Exception as e:
            print(f"\n✗ Failed to retrieve context: {e}")

    def show_sources(self):
        """Show sources from last answer."""
        if not self.last_response:
            print("\nNo previous answer to show sources for.")
            return

        self.print_header("Sources")

        if not self.last_response.sources:
            print("\nNo sources available.")
            return

        for i, source in enumerate(self.last_response.sources, 1):
            print(f"\n{i}. {source['type']}: {source['name']}")

    def show_reasoning(self):
        """Show reasoning trail from last answer."""
        if not self.last_response:
            print("\nNo previous answer to show reasoning for.")
            return

        self.print_header("Reasoning Trail")

        if not self.last_response.reasoning_trail:
            print("\nNo reasoning trail available.")
            return

        for i, step in enumerate(self.last_response.reasoning_trail, 1):
            print(f"\n{i}. {step}")

    def show_confidence(self):
        """Show confidence breakdown."""
        if not self.last_response:
            print("\nNo previous answer to show confidence for.")
            return

        self.print_header("Confidence Breakdown")

        confidence = self.last_response.confidence
        confidence_level = "HIGH" if confidence >= 0.9 else "MEDIUM" if confidence >= 0.7 else "LOW"

        print(f"""
Overall Confidence: {confidence:.2f} ({confidence_level})

Confidence Level Interpretation:
- HIGH (0.9+):     Strong evidence from multiple sources
- MEDIUM (0.7-0.9): Good evidence but with some uncertainty
- LOW (<0.7):      Limited evidence or conflicting information

This confidence score is calculated based on:
1. Quality and number of sources
2. Neurosymbolic reasoning results
3. Validation outcomes
4. Source attribution in answer
""")

    def reset_conversation(self):
        """Reset conversation history."""
        self.conversation_history = []
        self.last_response = None
        print("\n✓ Conversation history cleared")

    async def process_question(self, question: str):
        """Process a user question."""
        print("\n🤔 Thinking...")

        try:
            # Query the chat service
            response = await self.chat_service.query(
                question=question,
                conversation_history=self.conversation_history
            )

            # Store response
            self.last_response = response

            # Add to conversation history
            self.conversation_history.append(Message(role="user", content=question))
            self.conversation_history.append(Message(role="assistant", content=response.answer))

            # Display answer
            self.print_header("Answer")
            print(f"\n{response.answer}\n")

            # Display confidence
            confidence_label = "HIGH" if response.confidence >= 0.9 else "MEDIUM" if response.confidence >= 0.7 else "LOW"
            print(f"Confidence: {response.confidence:.2f} ({confidence_label})")

            # Display related concepts
            if response.related_concepts:
                print(f"\nRelated concepts: {', '.join(response.related_concepts)}")

            # Display query time
            print(f"\nQuery time: {response.query_time_seconds:.2f}s")

        except Exception as e:
            print(f"\n✗ Error processing question: {e}")
            logger.error("Question processing failed", exc_info=True)

    async def run(self):
        """Run the interactive chat loop."""
        while True:
            try:
                # Get user input
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    command = user_input.lower()

                    if command == "/help":
                        self.show_help()
                    elif command == "/context":
                        await self.show_context()
                    elif command == "/sources":
                        self.show_sources()
                    elif command == "/reasoning":
                        self.show_reasoning()
                    elif command == "/confidence":
                        self.show_confidence()
                    elif command == "/reset":
                        self.reset_conversation()
                    elif command == "/quit":
                        print("\n👋 Goodbye!\n")
                        break
                    else:
                        print(f"\n✗ Unknown command: {command}")
                        print("Type /help for available commands")

                else:
                    # Process question
                    await self.process_question(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!\n")
                break
            except EOFError:
                print("\n\n👋 Goodbye!\n")
                break
            except Exception as e:
                print(f"\n✗ Unexpected error: {e}")
                logger.error("Chat loop error", exc_info=True)


async def main():
    """Main entry point."""
    try:
        demo = InteractiveChatDemo()
        await demo.run()
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        logger.error("Demo initialization failed", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
