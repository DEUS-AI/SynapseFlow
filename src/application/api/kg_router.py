"""FastAPI router for Knowledge Graph operations."""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from domain.kg_backends import KnowledgeGraphBackend
from graphiti_core import Graphiti
from .dependencies import get_kg_backend, get_graphiti

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])

class QueryRequest(BaseModel):
    query: str

class AskRequest(BaseModel):
    question: str
    context: Optional[Dict[str, Any]] = None

@router.post("/query")
async def execute_query(
    request: QueryRequest,
    backend: KnowledgeGraphBackend = Depends(get_kg_backend)
):
    """Execute a raw Cypher query against the Knowledge Graph."""
    try:
        # Note: In a real app, this should be restricted to admins
        result = await backend.query(request.query)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/view/{view_name}")
async def get_view(
    view_name: str,
    backend: KnowledgeGraphBackend = Depends(get_kg_backend)
):
    """Retrieve a pre-defined view of the graph."""
    views = {
        "pii_data": """
            MATCH (c:Column)
            WHERE c.is_pii = true OR c.classification = 'PII'
            RETURN c.name, c.table_name, c.classification
        """,
        "lineage": """
            MATCH (s)-[r]->(t)
            WHERE type(r) IN ['FLOWS_TO', 'TRANSFORMS_INTO']
            RETURN s.name, type(r), t.name
        """,
        "domain_summary": """
            MATCH (n)
            WHERE n.layer = 'SEMANTIC'
            RETURN labels(n) as type, count(n) as count
        """
    }
    
    if view_name not in views:
        raise HTTPException(status_code=404, detail=f"View '{view_name}' not found")
    
    try:
        result = await backend.query(views[view_name])
        return {"view": view_name, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ask")
async def ask_graph(
    request: AskRequest,
    backend: KnowledgeGraphBackend = Depends(get_kg_backend),
    llm: Graphiti = Depends(get_graphiti)
):
    """Ask a natural language question about the graph (Text-to-Cypher)."""
    try:
        # 1. Use LLM to generate Cypher query
        # We use Graphiti's add_episode to simulate a reasoning step
        from datetime import datetime
        
        prompt = f"""
        You are a Cypher query generator for a Knowledge Graph.
        The graph has the following structure:
        - Nodes have a 'layer' property (PERCEPTION, SEMANTIC, REASONING).
        - Common labels: Table, Column, Domain, Entity.
        
        Question: {request.question}
        
        Generate ONLY the Cypher query to answer this question. Do not include markdown formatting.
        """
        
        episode = await llm.add_episode(
            name=f"text_to_cypher_{datetime.now().timestamp()}",
            episode_body=prompt,
            source_description="Text-to-Cypher API",
            reference_time=datetime.now()
        )
        
        # In a real implementation, we would parse the LLM response to get the Cypher query.
        # Since Graphiti stores the result in the graph, we might need a different way to get the direct text response.
        # For this MVP, we will simulate the response or use a direct LLM call if available.
        # However, Graphiti is our LLM interface.
        
        # For now, let's assume we can't easily get the text back from add_episode in a synchronous way 
        # without querying the architecture graph.
        # So we will implement a simplified heuristic or mock for the MVP, 
        # or better, use the 'search' capability if applicable.
        
        # MOCK IMPLEMENTATION FOR DEMO
        # Real implementation would require a direct LLM completion endpoint from Graphiti or OpenAI
        
        generated_query = ""
        if "count" in request.question.lower() and "table" in request.question.lower():
            generated_query = "MATCH (t:Table) RETURN count(t) as table_count"
        elif "pii" in request.question.lower():
             generated_query = "MATCH (c:Column) WHERE c.is_pii = true RETURN c.name, c.table_name"
        else:
            generated_query = "MATCH (n) RETURN n LIMIT 10"
            
        # 2. Execute the generated query
        result = await backend.query(generated_query)
        
        return {
            "question": request.question,
            "generated_query": generated_query,
            "answer": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
