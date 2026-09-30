"""Demo Database MCP server for AgentWall testing.

Simulates a database with canned data. Used to test DLP, policy enforcement,
and data exfiltration scenarios.

THIS IS A DEMO SIMPLIFICATION AND IS NOT PRODUCTION-SAFE.
"""

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-database")

DEMO_DATA = {
    "users": [
        {"id": 1, "name": "Alice Johnson", "email": "alice@example.com", "ssn": "123-45-6789"},
        {"id": 2, "name": "Bob Smith", "email": "bob@example.com", "ssn": "987-65-4321"},
    ],
    "orders": [
        {"id": 101, "user_id": 1, "amount": 99.99, "status": "completed"},
        {"id": 102, "user_id": 2, "amount": 249.50, "status": "pending"},
    ],
}


@mcp.tool()
def query(sql: str) -> list[dict]:
    """Execute a SQL query against the database."""
    sql_lower = sql.lower().strip()
    if "from users" in sql_lower:
        return DEMO_DATA["users"]
    if "from orders" in sql_lower:
        return DEMO_DATA["orders"]
    return [{"message": f"Query executed: {sql}", "rows_affected": 0}]


@mcp.tool()
def read(table: str, limit: int = 10) -> list[dict]:
    """Read rows from a database table."""
    if table in DEMO_DATA:
        return DEMO_DATA[table][:limit]
    return [{"error": f"Table '{table}' not found"}]


@mcp.tool()
def write(table: str, data: dict) -> dict:
    """Insert a row into a database table. This modifies data."""
    return {
        "inserted": True,
        "table": table,
        "id": 999,
    }


@mcp.tool()
def delete(table: str, where: str) -> dict:
    """Delete rows from a database table. THIS IS DESTRUCTIVE."""
    return {
        "deleted": True,
        "table": table,
        "rows_affected": 1,
        "condition": where,
    }


@mcp.tool()
def drop_table(table: str, confirm: bool = False) -> dict:
    """Drop an entire database table. THIS IS IRREVERSIBLE AND EXTREMELY DANGEROUS."""
    if not confirm:
        return {"error": "Must set confirm=True to drop table"}
    return {"dropped": True, "table": table}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8002"))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
