"""Command-line interface for the multi-agent system."""

from __future__ import annotations

import asyncio
import os
import typer
from dotenv import load_dotenv
from composition_root import (
    bootstrap_command_bus,
    bootstrap_graphiti,
    bootstrap_knowledge_management,
    AGENT_REGISTRY,
    create_modeling_command_handler,
    create_generate_metadata_command_handler,
)
from application.commands.agent_commands import (
    RunAgentCommand,
    RunAgentHandler,
    StartProjectCommand,
)
from application.commands.echo_command import EchoCommand
from application.commands.file_commands import CreateFileCommand, ReadFileCommand
from application.commands.shell_commands import ExecuteShellCommand
from application.commands.modeling_command import ModelingCommand
from application.commands.metadata_command import GenerateMetadataCommand
from application.agent_runner import AgentRunner
from domain.communication import Message
from infrastructure.communication.memory_channel import InMemoryCommunicationChannel

# --- Environment Loading ---
load_dotenv()

# --- Singletons ---
# These are created once and shared across the application.
COMMAND_BUS = bootstrap_command_bus()
# For now, we use an in-memory channel. This would be replaced by a real
# implementation (e.g., Google A2A) in a production scenario.
COMMUNICATION_CHANNEL = InMemoryCommunicationChannel()


# --- Typer App ---
app = typer.Typer(
    help="A multi-agent system for software development.",
    add_completion=False,
)

# --- CLI Commands ---


@app.command()
def echo(text: str):
    """Prints the given text back to the console."""
    result = asyncio.run(COMMAND_BUS.dispatch(EchoCommand(text=text)))
    typer.echo(result)


@app.command("create-file")
def create_file(path: str, content: str):
    """Creates a file at the specified path with the given content."""
    result = asyncio.run(COMMAND_BUS.dispatch(CreateFileCommand(path=path, content=content)))
    typer.echo(result)


@app.command("read-file")
def read_file(path: str):
    """Reads and prints the content of the specified file."""
    result = asyncio.run(COMMAND_BUS.dispatch(ReadFileCommand(path=path)))
    typer.echo(result)


@app.command("execute-shell")
def execute_shell(command: str):
    """Executes a shell command."""
    result = asyncio.run(COMMAND_BUS.dispatch(ExecuteShellCommand(command=command)))
    typer.echo(result)


@app.command("model")
def model(
    dda_path: str = typer.Option(..., "--dda-path", help="Path to the DDA document"),
    domain: str = typer.Option(None, "--domain", help="Explicit domain specification"),
):
    """Process DDA document and create/update knowledge graph."""
    
    async def run_modeling():
        # Initialize knowledge management components
        # We use the configured backend (Neo4j/Graphiti/InMemory)
        kg_backend, _ = await bootstrap_knowledge_management()
        
        # Create a temporary Graphiti instance for LLM/Enrichment
        graph = await bootstrap_graphiti("modeling-cli")
        
        # Register the metadata generation command handler
        metadata_handler = create_generate_metadata_command_handler(graph, kg_backend)
        COMMAND_BUS.register(GenerateMetadataCommand, metadata_handler)
        
        # Create and execute the metadata command
        command = GenerateMetadataCommand(
            dda_path=dda_path,
            domain=domain
        )
        
        return await COMMAND_BUS.dispatch(command)
    
    result = asyncio.run(run_modeling())
    
    if result["success"]:
        typer.echo(f"✅ Metadata Generation & Enrichment completed successfully!")
        typer.echo(f"   Domain: {result.get('domain', 'Unknown')}")
        
        # The result from MetadataGenerationWorkflow is a simple dict
        # We can add more details if the workflow returns them
        if 'stats' in result:
             stats = result['stats']
             typer.echo(f"   Entities: {stats.get('entities', 0)}")
             typer.echo(f"   Nodes: {stats.get('nodes', 0)}")
             typer.echo(f"   Relationships: {stats.get('relationships', 0)}")
        
        typer.echo(f"\n💡 Knowledge Graph is now populated with enriched data.")
        
    else:
        typer.echo(f"❌ Modeling failed:")
        for error in result.get('errors', []):
            typer.echo(f"   - {error}")
        
        raise typer.Exit(code=1)


@app.command("ingest-doc")
def ingest_doc(
    file_path: str = typer.Option(..., "--file-path", help="Path to the document (PDF, DOCX, etc.)"),
    source_name: str = typer.Option(None, "--source", help="Human-readable name for the document"),
    chunk_size: int = typer.Option(1500, "--chunk-size", help="Target chunk size in characters"),
):
    """Ingest a document into the knowledge graph with embeddings."""
    
    async def run_ingestion():
        from application.services.document_service import DocumentService
        
        # Initialize knowledge management components
        kg_backend, _ = await bootstrap_knowledge_management()
        
        # Create document service
        doc_service = DocumentService(
            kg_backend=kg_backend,
            chunk_size=chunk_size
        )
        
        # Ingest the document
        document = await doc_service.ingest_document(
            file_path=file_path,
            source_name=source_name
        )
        
        return document
    
    try:
        document = asyncio.run(run_ingestion())
        
        typer.echo(f"\n✅ Document Ingested Successfully!")
        typer.echo(f"   ID: {document.id}")
        typer.echo(f"   Name: {document.name}")
        typer.echo(f"   Chunks: {document.chunk_count}")
        typer.echo(f"   Hash: {document.content_hash}")
        typer.echo(f"\n💡 View in Neo4j:")
        typer.echo(f"   MATCH (d:Document {{id: '{document.id}'}})-[:HAS_CHUNK]->(c) RETURN d, c")
        
    except Exception as e:
        typer.echo(f"❌ Ingestion failed: {e}")
        raise typer.Exit(code=1)


@app.command("search-docs")
def search_docs(
    query: str = typer.Option(..., "--query", "-q", help="Search query"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return"),
):
    """Search ingested documents using vector similarity."""
    
    async def run_search():
        from application.services.document_service import DocumentService
        
        # Initialize with no kg_backend (we only need FAISS for search)
        doc_service = DocumentService(kg_backend=None)
        
        # Search
        results = await doc_service.search_similar(query=query, top_k=top_k)
        return results
    
    results = asyncio.run(run_search())
    
    if not results:
        typer.echo("No results found. Have you ingested any documents?")
        return
    
    typer.echo(f"\n🔍 Search Results for: '{query}'\n")
    for r in results:
        typer.echo(f"[{r['rank']}] Score: {r['score']:.3f} | Chunk: {r['chunk_id']}")
        typer.echo(f"    {r['text'][:200]}...")
        typer.echo("")


@app.command("ask")
def ask(
    question: str = typer.Option(..., "--question", "-q", help="Question to ask"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of chunks to retrieve"),
    no_graph: bool = typer.Option(False, "--no-graph", help="Skip graph context enrichment"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show sources and context"),
):
    """Ask a question using RAG (vector search + graph context + LLM)."""
    
    async def run_query():
        from application.services.document_service import DocumentService
        from application.services.rag_service import RAGService
        
        # Initialize components
        kg_backend, _ = await bootstrap_knowledge_management()
        doc_service = DocumentService(kg_backend=None)  # FAISS only
        
        # Create RAG service
        rag = RAGService(
            document_service=doc_service,
            kg_backend=kg_backend
        )
        
        # Query
        response = await rag.query(
            question=question,
            top_k=top_k,
            include_graph_context=not no_graph
        )
        
        return response
    
    typer.echo(f"\n🤔 Asking: {question}\n")
    typer.echo("─" * 60)
    
    response = asyncio.run(run_query())
    
    # Display answer
    typer.echo(f"\n📝 Answer (confidence: {response.confidence:.0%}):\n")
    typer.echo(response.answer)
    
    if verbose:
        typer.echo("\n" + "─" * 60)
        typer.echo("\n📚 Sources:")
        for src in response.sources:
            typer.echo(f"  • {src['chunk_id']} (score: {src['score']:.3f})")
        
        if response.graph_context:
            typer.echo("\n🔗 Graph Context:")
            seen = set()
            for ctx in response.graph_context:
                key = f"{ctx['entity']} ({ctx['type']})"
                if key not in seen:
                    typer.echo(f"  • {key}")
                    seen.add(key)


@app.command("start-project")
def start_project(
    goal: str = typer.Option(..., "--goal", help="The high-level goal of the project.")
):
    """
    Initiates a new project by sending a task to the Architect agent.
    """
    arx_agent_id = "data_architect-agent"

    async def send_task():
        project_command = StartProjectCommand(project_goal=goal)
        message = Message(
            sender_id="cli", receiver_id=arx_agent_id, content=project_command
        )
        await COMMUNICATION_CHANNEL.send(message)
        typer.echo(f"Project goal sent to agent '{arx_agent_id}'.")

    asyncio.run(send_task())


@app.command("run-agent")
def run_agent(
    role: str = typer.Option(..., "--role", help="The role of the agent to run.")
):
    """
    Runs an agent with a specific role until interrupted.
    """
    if role not in AGENT_REGISTRY:
        typer.echo(f"Error: No agent found for role '{role}'.")
        typer.echo(f"Available roles: {list(AGENT_REGISTRY.keys())}")
        raise typer.Exit(code=1)

    async def _run_agent_async():
        # --- Dynamic Agent and Handler Creation ---
        agent_factory = AGENT_REGISTRY[role]
        agent_id = f"{role}-agent"

        # Use agent_id as the namespace for Graphiti graph
        graph = await bootstrap_graphiti(agent_id)

        # Special handling for agents with extra dependencies
        if role == "data_architect":
            agent = agent_factory(
                agent_id=agent_id,
                command_bus=COMMAND_BUS,
                communication_channel=COMMUNICATION_CHANNEL,
                graph=graph,
                # llm argument removed as it's not in the factory signature
                url="http://localhost:8001",
            )
        elif role == "data_engineer":
            # Initialize knowledge management components
            kg_backend, event_bus = await bootstrap_knowledge_management()
            
            # Register GenerateMetadataCommand handler
            metadata_handler = create_generate_metadata_command_handler(graph, kg_backend)
            COMMAND_BUS.register(GenerateMetadataCommand, metadata_handler)
            
            agent = agent_factory(
                agent_id=agent_id,
                command_bus=COMMAND_BUS,
                communication_channel=COMMUNICATION_CHANNEL,
                graph=graph,
                url="http://localhost:8002",
                kg_backend=kg_backend,
                event_bus=event_bus,
            )
        elif role == "knowledge_manager":
            # Initialize knowledge management components
            kg_backend, event_bus = await bootstrap_knowledge_management()

            agent = agent_factory(
                agent_id=agent_id,
                command_bus=COMMAND_BUS,
                communication_channel=COMMUNICATION_CHANNEL,
                kg_backend=kg_backend,
                event_bus=event_bus,
                llm=graph, # Knowledge Manager needs LLM for reasoning
            )
        elif role == "medical_assistant":
            # Initialize patient memory service
            from composition_root import bootstrap_patient_memory
            patient_memory_service = await bootstrap_patient_memory()

            agent = agent_factory(
                agent_id=agent_id,
                command_bus=COMMAND_BUS,
                communication_channel=COMMUNICATION_CHANNEL,
                patient_memory_service=patient_memory_service,
                url="http://localhost:8003",
            )
        else:
            agent = agent_factory(
                agent_id=agent_id,
                command_bus=COMMAND_BUS,
                communication_channel=COMMUNICATION_CHANNEL,
                url="http://localhost:8000",
            )

        runner = AgentRunner(agent)
        handler = RunAgentHandler(runner)

        # The handler is registered just-in-time for this specific agent instance.
        COMMAND_BUS.register(RunAgentCommand, handler)

        typer.echo(f"Starting agent with role: {role} (Press Ctrl+C to stop)")
        try:
            await COMMAND_BUS.dispatch(RunAgentCommand(role=role))
        except asyncio.CancelledError:
            typer.echo(f"\nStopping agent {role}...")
            runner.stop()
        finally:
            typer.echo(f"Agent {role} has been shut down.")

    try:
        asyncio.run(_run_agent_async())
    except KeyboardInterrupt:
        pass


@app.command("create-template")
def create_template(
    name: str = typer.Option(..., "--name", help="Name for the DDA template"),
    output_path: str = typer.Option(None, "--output-path", help="Output path for the template"),
):
    """Create a new DDA template with the given name."""
    
    template_content = f"""# Data Delivery Agreement (DDA) - {name}

## Document Information
- **Domain**: {name}
- **Stakeholders**: [List key stakeholders]
- **Data Owner**: [Data owner name/role]
- **Effective Date**: [YYYY-MM-DD]
- **Review Cycle**: [Monthly/Quarterly/Annually]

## Business Context
[Describe the business context and purpose of this domain]

## Data Entities

### [Entity Name]
- **Description**: [Entity description]
- **Key Attributes**:
  - [Attribute 1] (Primary Key)
  - [Attribute 2]
  - [Attribute 3]
- **Business Rules**:
  - [Business rule 1]
  - [Business rule 2]

### [Entity Name 2]
- **Description**: [Entity description]
- **Key Attributes**:
  - [Attribute 1] (Primary Key)
  - [Attribute 2] (Foreign Key)
  - [Attribute 3]
- **Business Rules**:
  - [Business rule 1]
  - [Business rule 2]

## Relationships

### [Relationship Category]
- **[Entity 1]** → **[Entity 2]** (1:N)
  - [Relationship description]
  - [Constraints]

- **[Entity 1]** → **[Entity 3]** (M:N)
  - [Relationship description]
  - [Constraints]

## Data Quality Requirements

### Completeness
- [Completeness requirement 1]
- [Completeness requirement 2]

### Accuracy
- [Accuracy requirement 1]
- [Accuracy requirement 2]

### Timeliness
- [Timeliness requirement 1]
- [Timeliness requirement 2]

## Access Patterns

### Common Queries
1. [Query description 1]
2. [Query description 2]
3. [Query description 3]

### Performance Requirements
- [Performance requirement 1]
- [Performance requirement 2]

## Data Governance

### Privacy
- [Privacy requirement 1]
- [Privacy requirement 2]

### Security
- [Security requirement 1]
- [Security requirement 2]

### Compliance
- [Compliance requirement 1]
- [Compliance requirement 2]

## Success Metrics
- [Success metric 1]
- [Success metric 2]
- [Success metric 3]
"""
    
    # Determine output path
    if output_path:
        file_path = output_path
    else:
        file_path = f"examples/{name.lower().replace(' ', '_')}_dda.md"
    
    # Create directory if it doesn't exist
    import os
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Write template to file
    with open(file_path, 'w') as f:
        f.write(template_content)
    
    typer.echo(f"✅ DDA template created: {file_path}")
    typer.echo(f"📝 Template name: {name}")
    typer.echo(f"🔧 Next steps: Edit the template with domain-specific information")


if __name__ == "__main__":
    app()
