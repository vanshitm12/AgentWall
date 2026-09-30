"""Demo GitHub MCP server for AgentWall testing.

This is NOT a real GitHub integration. It simulates GitHub MCP tools
with canned responses so we can test AgentWall's proxy, policy, and
audit systems without requiring real GitHub credentials.

THIS IS A DEMO SIMPLIFICATION AND IS NOT PRODUCTION-SAFE.
"""

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-github")


@mcp.tool()
def read_file(repo: str, path: str, ref: str = "main") -> str:
    """Read a file from a GitHub repository."""
    return f"# Contents of {path} from {repo}@{ref}\n\ndef main():\n    print('Hello from {repo}')\n"


@mcp.tool()
def list_files(repo: str, path: str = "", ref: str = "main") -> list[str]:
    """List files in a GitHub repository directory."""
    return [
        f"{path}/README.md",
        f"{path}/src/main.py",
        f"{path}/src/utils.py",
        f"{path}/tests/test_main.py",
    ]


@mcp.tool()
def create_pull_request(
    repo: str, title: str, body: str, head: str, base: str = "main"
) -> dict:
    """Create a pull request in a GitHub repository."""
    return {
        "number": 182,
        "title": title,
        "state": "open",
        "html_url": f"https://github.com/{repo}/pull/182",
        "head": head,
        "base": base,
    }


@mcp.tool()
def merge_pull_request(repo: str, pull_number: int, merge_method: str = "squash") -> dict:
    """Merge a pull request. This is a high-risk operation affecting production."""
    return {
        "merged": True,
        "message": f"Pull request #{pull_number} merged via {merge_method}",
        "sha": "abc123def456",
    }


@mcp.tool()
def delete_repo(repo: str, confirm: bool = False) -> dict:
    """Delete a GitHub repository. THIS IS IRREVERSIBLE AND EXTREMELY DANGEROUS."""
    if not confirm:
        return {"error": "Must set confirm=True to delete repository"}
    return {"deleted": True, "repo": repo}


@mcp.tool()
def create_issue(repo: str, title: str, body: str, labels: list[str] | None = None) -> dict:
    """Create an issue in a GitHub repository."""
    return {
        "number": 42,
        "title": title,
        "state": "open",
        "html_url": f"https://github.com/{repo}/issues/42",
        "labels": labels or [],
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
