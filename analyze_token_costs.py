"""
Analyze token costs for different operations in the system.

OpenAI Pricing (as of 2024):
- gpt-4o-mini:
  - Input: $0.150 per 1M tokens
  - Output: $0.600 per 1M tokens
- text-embedding-3-small:
  - $0.020 per 1M tokens
"""

print("=" * 70)
print("  Token Cost Analysis")
print("=" * 70)

# PDF Ingestion (per PDF)
print("\n1. PDF Ingestion (per document):")
print("   - Markdown conversion: Free (local)")
print("   - Entity extraction (LLM): ~2,000 input + 500 output tokens")
print("     Cost: $0.0003 + $0.0003 = $0.0006 per PDF")
print("   - Embeddings (9 chunks): 9 * 1,500 tokens = 13,500 tokens")
print("     Cost: $0.00027 per PDF")
print("   → Total per PDF: ~$0.00087")

# For all 18 PDFs
print("\n   For 18 PDFs:")
print(f"   → Total: 18 * $0.00087 = $0.016 (one-time cost)")

# Chat Queries
print("\n2. Chat Query (per question):")
print("   - Entity extraction: ~100 input + 50 output tokens")
print("     Cost: $0.000015 + $0.00003 = $0.000045")
print("   - Embeddings for RAG search: ~20 tokens")
print("     Cost: $0.0000004")
print("   - Answer generation: ~2,500 input + 500 output tokens")
print("     Cost: $0.000375 + $0.0003 = $0.000675")
print("   → Total per query: ~$0.00072")

# High volume scenarios
print("\n3. Scale Analysis:")
print("\n   1,000 queries/day:")
print(f"     Daily: 1,000 * $0.00072 = $0.72")
print(f"     Monthly: $0.72 * 30 = $21.60")

print("\n   10,000 queries/day:")
print(f"     Daily: 10,000 * $0.00072 = $7.20")
print(f"     Monthly: $7.20 * 30 = $216")

print("\n   100,000 queries/day:")
print(f"     Daily: 100,000 * $0.00072 = $72")
print(f"     Monthly: $72 * 30 = $2,160")

# Breakdown by operation
print("\n4. Cost Breakdown by Operation:")
print("   Per Chat Query:")
print("     - Entity extraction: 6% ($0.000045)")
print("     - Embeddings: 0.06% ($0.0000004)")
print("     - Answer generation: 93.8% ($0.000675)")
print("   → Answer generation is the most expensive!")

# Local SLM savings
print("\n5. Potential Savings with Local SLM:")
print("\n   Option A: Replace entity extraction only")
print("     Savings: 6% of query cost = $0.000045 per query")
print("     At 10,000 queries/day: $1.35/month saved")
print("     → Small impact, low priority")

print("\n   Option B: Replace embeddings only")
print("     Savings: 0.06% of query cost = $0.0000004 per query")
print("     At 10,000 queries/day: $0.012/month saved")
print("     → Negligible impact")

print("\n   Option C: Replace answer generation (keep OpenAI for extraction)")
print("     Savings: 93.8% of query cost = $0.000675 per query")
print("     At 10,000 queries/day: $202.50/month saved")
print("     → Highest impact! But answer quality may suffer")

print("\n   Option D: Hybrid approach")
print("     - Local SLM for entity extraction (6%)")
print("     - Local embeddings for RAG (0.06%)")
print("     - OpenAI for answer generation (93.8%)")
print("     Savings: 6.06% of query cost")
print("     At 10,000 queries/day: $13.10/month saved")
print("     → Minimal savings, not worth complexity")

# Recommendations
print("\n" + "=" * 70)
print("  Recommendations")
print("=" * 70)

print("\n1. CURRENT SCALE (< 1,000 queries/day):")
print("   → Keep using OpenAI for everything")
print("   → Cost: < $1/day - not worth optimizing yet")

print("\n2. MEDIUM SCALE (1,000 - 10,000 queries/day):")
print("   → Still use OpenAI")
print("   → Cost: $1-$7/day - reasonable for quality you get")
print("   → Focus on: Caching results, deduplicating queries")

print("\n3. HIGH SCALE (> 10,000 queries/day):")
print("   → Consider local SLM for ANSWER GENERATION")
print("   → Keep OpenAI for entity extraction (high quality needed)")
print("   → Models to consider:")
print("     - Llama 3 8B (good quality/speed balance)")
print("     - Mistral 7B (fast, good for chat)")
print("     - Phi-3 Mini (very fast, 3.8B params)")
print("   → Cost: $200+/month saved, but need GPU/hosting")

print("\n4. OPTIMIZATION PRIORITIES (by ROI):")
print("   1. Query caching (highest ROI)")
print("   2. Result deduplication")
print("   3. Reduce context size (trim graph results)")
print("   4. Local answer generation (if > 10k queries/day)")
print("   5. Local entity extraction (very low ROI)")

print("\n" + "=" * 70)

