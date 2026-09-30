# AgentWall — Progress Log

## Phase 0: Discovery & Design

**Status:** In Progress

### Completed
- Repository initialized
- Architecture decisions made (7 ADRs)
- Product spec written
- Architecture document written
- Threat model written
- MVP scope defined
- Project structure scaffolded
- Docker Compose skeleton created

### Decisions Made
1. **MCP Proxy:** Full reverse proxy (ADR-001)
2. **MCP Transport:** Streamable HTTP agent-facing + both downstream (ADR-002)
3. **Policy Engine:** Cedar (AWS) (ADR-003)
4. **Agent Identity:** API Key + Session Token (ADR-004)
5. **Storage:** PostgreSQL durable + Redis ephemeral (ADR-005)
6. **App Architecture:** Single FastAPI service + Next.js dashboard (ADR-006)
7. **Audit Sensitivity:** Configurable levels, ARGS_ONLY default (ADR-007)

### Next
- Complete ADR documents
- Set up Python project (pyproject.toml, dependencies)
- Set up Next.js project
- Configure Docker Compose
- Begin Phase 1: MCP Proxy

---

## Phase 1: MCP Proxy
**Status:** Not Started

## Phase 2: Registries
**Status:** Not Started

## Phase 3: Policy Engine
**Status:** Not Started

## Phase 4: Approval System
**Status:** Not Started

## Phase 5: Audit System
**Status:** Not Started

## Phase 6: Risk Engine
**Status:** Not Started

## Phase 7: DLP
**Status:** Not Started

## Phase 8: Kill Switch
**Status:** Not Started

## Phase 9: Attack Playground
**Status:** Not Started

## Phase 10: Dashboard
**Status:** Not Started
