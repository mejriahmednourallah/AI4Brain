# External integration status

The full implementation goal remains PAUSED at the user's request. Current work is UI concept review and Neo4j setup.

## Neo4j working

Verified Neo4j5.26.32 Community in container minyar-neo4j-1. Only this container is running. HTTP http://127.0.0.1:7474 and Bolt bolt://127.0.0.1:7687 bind to loopback. Credentials are in ignored .env and are never printed. Local .env now has NEO4J_ENABLED=true; example config remains opt-in.

scripts/verify_neo4j_live.py authenticated, verified connectivity/RETURN1, mirrored actual saved SQLite automated-QA evidence through graph_service.py, queried typed relationships/evidence IDs, and checked second-sync idempotency. Result:59nodes,54relationships, reasoning83.33 from6savedbaselineattempts. These are software QA observations, not measurements of the human user. Exact result:output/verification/neo4j-live.json.

The graph adapter is live-tested. The graph UI/API integration remains part of paused implementation and must not be described as complete. No unrelated Docker workload was restarted intentionally; final docker ps showed only minyar-neo4j-1 healthy.

To start this service later when Docker engine is already running: docker compose up -d neo4j. To stop only this service: docker compose stop neo4j. Application startup scripts do not start Docker.

## Coach

No LLM key/model assumed. Optional validated LLM wrapper and offline fallback remain planned; no live provider call is claimed.
