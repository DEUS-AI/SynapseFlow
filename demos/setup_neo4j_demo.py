#!/usr/bin/env python3
"""
Neo4j Demo Setup Script

This script helps you set up Neo4j for the SynapseFlow demo.
It checks your Neo4j connection and provides setup instructions.
"""

import os
import asyncio
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.infrastructure.neo4j_backend import create_neo4j_backend


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"🎯 {title}")
    print(f"{'='*60}")


def print_step(step: int, description: str):
    """Print a formatted step."""
    print(f"\n📋 Step {step}: {description}")
    print("-" * 50)


def print_success(message: str):
    """Print a success message."""
    print(f"✅ {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"❌ {message}")


def print_info(message: str):
    """Print an info message."""
    print(f"ℹ️  {message}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"⚠️  {message}")


async def test_neo4j_connection():
    """Test Neo4j connection."""
    try:
        print("🔍 Testing Neo4j connection...")
        
        backend = await create_neo4j_backend()
        
        # Test basic connectivity
        result = await backend.query("RETURN 1 as test")
        
        if result and "nodes" in result:
            print_success("Neo4j connection successful!")
            print_info("   Basic query execution: ✅")
            
            # Test entity creation
            await backend.add_entity("test_entity", {"name": "Test", "type": "demo"})
            print_info("   Entity creation: ✅")
            
            # Test entity retrieval
            entity = await backend.get_entity("test_entity")
            if entity:
                print_info("   Entity retrieval: ✅")
            
            # Clean up test entity
            await backend.delete_entity("test_entity")
            print_info("   Entity deletion: ✅")
            
            await backend.close()
            return True
            
    except Exception as e:
        print_error(f"Neo4j connection failed: {e}")
        return False


def check_environment_variables():
    """Check if Neo4j environment variables are set."""
    print_step(1, "Checking environment variables")
    
    required_vars = {
        "NEO4J_URI": "Neo4j connection URI",
        "NEO4J_USERNAME": "Neo4j username", 
        "NEO4J_PASSWORD": "Neo4j password"
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            print_success(f"{var}: {value}")
        else:
            print_warning(f"{var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print_error(f"Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    return True


def show_neo4j_setup_instructions():
    """Show instructions for setting up Neo4j."""
    print_header("Neo4j Setup Instructions")
    
    print_step(1, "Install Neo4j")
    print("""
   Option A: Docker (Recommended for demo)
   docker run -d \\
     --name neo4j-demo \\
     -p 7474:7474 -p 7687:7687 \\
     -e NEO4J_AUTH=neo4j/password \\
     -e NEO4J_PLUGINS='["apoc"]' \\
     neo4j:5.15-community
   
   Option B: Download from neo4j.com
   - Download Neo4j Desktop or Community Edition
   - Install and start the service
   """)
    
    print_step(2, "Set environment variables")
    print("""
   Add these to your .env file or export them:
   
   export NEO4J_URI="bolt://localhost:7687"
   export NEO4J_USERNAME="neo4j"
   export NEO4J_PASSWORD="password"
   
   Or create a .env file:
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=password
   """)
    
    print_step(3, "Verify connection")
    print("""
   - Neo4j should be running on port 7687 (Bolt)
   - Web interface available at http://localhost:7474
   - Default credentials: neo4j/password
   - First login will require password change
   """)
    
    print_step(4, "Test the demo")
    print("""
   Run the demo script:
   python multi_agent_dda_demo.py
   
   It should automatically detect Neo4j and use it!
   """)


def show_docker_quick_start():
    """Show Docker quick start commands."""
    print_header("Docker Quick Start")
    
    print("🐳 Quick Neo4j setup with Docker:")
    print("""
   # Start Neo4j
   docker run -d \\
     --name neo4j-demo \\
     -p 7474:7474 -p 7687:7687 \\
     -e NEO4J_AUTH=neo4j/password \\
     -e NEO4J_PLUGINS='["apoc"]' \\
     neo4j:5.15-community
   
   # Check if running
   docker ps | grep neo4j
   
   # View logs
   docker logs neo4j-demo
   
   # Stop Neo4j
   docker stop neo4j-demo
   
   # Remove container
   docker rm neo4j-demo
   """)
    
    print_info("Web interface: http://localhost:7474")
    print_info("Bolt connection: bolt://localhost:7687")
    print_info("Default credentials: neo4j/password")


def show_environment_file_template():
    """Show .env file template."""
    print_header("Environment File Template")
    
    env_content = """# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Optional: Neo4j Database
NEO4J_DATABASE=neo4j

# Other configurations
DEMO_PRESENTATION_MODE=false
DEMO_VERBOSE_OUTPUT=true
"""
    
    print("Create a .env file in your project root:")
    print("```")
    print(env_content)
    print("```")
    
    # Check if .env exists
    env_file = Path(".env")
    if env_file.exists():
        print_success(".env file already exists")
    else:
        print_warning(".env file not found - create one with the template above")


async def main():
    """Main setup function."""
    print_header("SynapseFlow Neo4j Demo Setup")
    
    print("This script helps you set up Neo4j for the SynapseFlow demo.")
    print("It will check your configuration and provide setup instructions.\n")
    
    # Check environment variables
    env_ok = check_environment_variables()
    
    if env_ok:
        print_step(2, "Testing Neo4j connection")
        connection_ok = await test_neo4j_connection()
        
        if connection_ok:
            print_header("🎉 Neo4j Setup Complete!")
            print_success("Your Neo4j is properly configured and ready for the demo!")
            print_info("Run: python multi_agent_dda_demo.py")
            print_info("The demo will automatically use Neo4j for persistent storage.")
        else:
            print_header("🔧 Neo4j Setup Required")
            print_error("Neo4j connection failed. Please follow the setup instructions.")
            show_neo4j_setup_instructions()
            show_docker_quick_start()
    else:
        print_header("🔧 Environment Setup Required")
        print_error("Environment variables are not properly configured.")
        show_environment_file_template()
        show_neo4j_setup_instructions()
    
    print_header("Next Steps")
    print("1. Set up Neo4j following the instructions above")
    print("2. Configure environment variables")
    print("3. Test connection with this script")
    print("4. Run the demo: python multi_agent_dda_demo.py")
    print("5. Enjoy persistent knowledge graph storage! 🚀")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Setup interrupted. Run again when ready!")
    except Exception as e:
        print_error(f"Setup failed: {e}")
        print_info("Check the error message above and try again.")
