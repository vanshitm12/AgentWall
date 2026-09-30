// Example Cedar policy for a "coding-agent"
// This agent can read GitHub files and create PRs,
// but merging requires approval and repo deletion is forbidden.

// Allow reading files from GitHub
permit(
    principal == Agent::"coding-agent",
    action == Action::"tool_call",
    resource == Tool::"github.read_file"
);

// Allow creating pull requests
permit(
    principal == Agent::"coding-agent",
    action == Action::"tool_call",
    resource == Tool::"github.create_pull_request"
);

// Merging PRs requires approval (handled by AgentWall when decision == APPROVAL)
// This permit is annotated; AgentWall checks the policy metadata for approval requirement
permit(
    principal == Agent::"coding-agent",
    action == Action::"tool_call",
    resource == Tool::"github.merge_pull_request"
);

// Deny repo deletion for all agents
forbid(
    principal,
    action == Action::"tool_call",
    resource == Tool::"github.delete_repo"
);
