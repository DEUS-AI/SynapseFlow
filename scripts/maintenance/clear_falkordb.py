from falkordb import FalkorDB

def clear_graph():
    client = FalkorDB(host='localhost', port=6379)
    graph = client.select_graph('knowledge_graph')
    
    print("Deleting all nodes and relationships...")
    graph.query("MATCH (n) DETACH DELETE n")
    print("Graph cleared.")

if __name__ == "__main__":
    clear_graph()
