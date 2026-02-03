"""RAG Query Service.

Retrieval-Augmented Generation pipeline that combines:
1. Vector search (FAISS) for relevant document chunks
2. Graph context (Neo4j) for related entities and metadata
3. LLM for generating answers
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os


@dataclass
class RAGResponse:
    """Response from the RAG pipeline."""
    answer: str
    sources: List[Dict[str, Any]]
    graph_context: List[Dict[str, Any]]
    confidence: float


class RAGService:
    """Retrieval-Augmented Generation service."""
    
    def __init__(
        self,
        document_service=None,
        kg_backend=None,
        model: str = "gpt-4o-mini"
    ):
        """Initialize the RAG service.
        
        Args:
            document_service: Document service for vector search
            kg_backend: Knowledge graph backend for context enrichment
            model: LLM model to use for generation
        """
        self.document_service = document_service
        self.kg_backend = kg_backend
        self.model = model
    
    async def query(
        self,
        question: str,
        top_k: int = 5,
        include_graph_context: bool = True
    ) -> RAGResponse:
        """Answer a question using RAG.
        
        Args:
            question: The user's question
            top_k: Number of chunks to retrieve
            include_graph_context: Whether to enrich with graph data
            
        Returns:
            RAGResponse with answer and sources
        """
        # 1. Retrieve relevant chunks from FAISS
        chunks = await self.document_service.search_similar(question, top_k=top_k)
        
        # 2. Get graph context (related entities from chunks)
        graph_context = []
        if include_graph_context and self.kg_backend and chunks:
            graph_context = await self._get_graph_context(chunks)
        
        # 3. Build prompt with context
        prompt = self._build_prompt(question, chunks, graph_context)
        
        # 4. Generate answer with LLM
        answer, confidence = await self._generate_answer(prompt, question)
        
        return RAGResponse(
            answer=answer,
            sources=[{"chunk_id": c["chunk_id"], "score": c["score"]} for c in chunks],
            graph_context=graph_context,
            confidence=confidence
        )
    
    async def _get_graph_context(
        self, 
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Retrieve graph context for the retrieved chunks."""
        context = []
        
        # Get entities mentioned in the chunks
        chunk_ids = [c["chunk_id"] for c in chunks]
        
        try:
            for chunk_id in chunk_ids[:3]:  # Limit to first 3 chunks for speed
                # Query for entities mentioned by this chunk
                query = """
                MATCH (c:Chunk {id: $chunk_id})-[:MENTIONS]->(e:ExtractedEntity)
                OPTIONAL MATCH (e)-[:LINKS_TO]->(m)
                RETURN e.name as entity, e.type as type, m.id as linked_to
                LIMIT 10
                """
                result = await self.kg_backend.query(query, {"chunk_id": chunk_id})
                
                # Extract from result
                if result and "nodes" in result:
                    for node_id, node_data in result.get("nodes", {}).items():
                        props = node_data.get("properties", {})
                        context.append({
                            "entity": props.get("name", node_id),
                            "type": props.get("type", "Unknown"),
                            "source": chunk_id
                        })
        except Exception as e:
            print(f"Warning: Could not get graph context: {e}")
        
        # Also get any related metadata nodes
        try:
            # Search for BusinessConcepts related to question
            query = """
            MATCH (c:BusinessConcept)
            RETURN c.name as name, labels(c) as labels
            LIMIT 10
            """
            result = await self.kg_backend.query(query, {})
            if result and "nodes" in result:
                for node_id, node_data in result.get("nodes", {}).items():
                    props = node_data.get("properties", {})
                    context.append({
                        "entity": props.get("name", node_id),
                        "type": "BusinessConcept",
                        "source": "knowledge_graph"
                    })
        except Exception:
            pass
        
        return context
    
    def _build_prompt(
        self,
        question: str,
        chunks: List[Dict[str, Any]],
        graph_context: List[Dict[str, Any]]
    ) -> str:
        """Build the prompt with retrieved context."""
        
        # Format document chunks
        chunks_text = "\n\n---\n\n".join([
            f"[Source: {c['chunk_id']} (relevance: {c['score']:.2f})]\n{c['text']}"
            for c in chunks
        ])
        
        # Format graph context
        if graph_context:
            entities = list(set([f"- {ctx['entity']} ({ctx['type']})" for ctx in graph_context]))
            graph_text = "\n".join(entities[:15])  # Limit to 15 entities
        else:
            graph_text = "(No graph context available)"
        
        prompt = f"""You are a helpful assistant with access to a knowledge graph about data architecture and business domains.

## Relevant Documents
{chunks_text}

## Related Entities from Knowledge Graph
{graph_text}

## Question
{question}

## Instructions
1. Answer the question based on the provided context
2. If the context doesn't contain enough information, say so
3. Reference specific sources when possible
4. Be concise but comprehensive

## Answer"""
        
        return prompt
    
    async def _generate_answer(
        self, 
        prompt: str, 
        question: str
    ) -> tuple[str, float]:
        """Generate answer using LLM."""
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            # Fallback without LLM
            return self._fallback_answer(prompt), 0.3
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert assistant for data architecture and business domain questions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
            # Estimate confidence based on response
            confidence = 0.8 if len(answer) > 100 else 0.6
            
            return answer, confidence
            
        except Exception as e:
            print(f"Warning: LLM generation failed: {e}")
            return self._fallback_answer(prompt), 0.3
    
    def _fallback_answer(self, prompt: str) -> str:
        """Generate a simple fallback answer without LLM."""
        # Extract the relevant text from prompt
        import re
        docs_match = re.search(r'## Relevant Documents\n(.+?)## Related Entities', prompt, re.DOTALL)
        
        if docs_match:
            docs_text = docs_match.group(1).strip()[:500]
            return f"Based on the retrieved documents:\n\n{docs_text}\n\n(Note: LLM not available for full answer generation)"
        
        return "Could not generate an answer. Please check that OPENAI_API_KEY is set."
