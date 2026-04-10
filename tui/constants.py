"""tui/constants.py — Slash command registry (single source of truth)."""

LOADING_MESSAGES = [
    "[~] Warming up the engines...",
    "[+] Crunching tokens...",
    "[?] Consulting the oracle...",
    "[^] Summoning intelligence...",
    "[~] Herding cats...",
    "[>] Connecting the dots...",
    "[#] Running the numbers...",
    "[*] Thinking really hard...",
    "[!] Boiling the ocean...",
]

SLASH_COMMANDS = [
    ("/attach <path>", "Attach a file to the next message"),
    ("/document add <path>", "Add a document to the project"),
    ("/document list", "List project documents"),
    ("/document remove <#>", "Remove a document by index"),
    ("/mcp add <url>", "Register a remote MCP server"),
    ("/mcp add local <name> [args]", "Register a local MCP server"),
    ("/mcp list", "List registered MCP servers"),
    ("/mcp remove <#>", "Remove an MCP server by index"),
    ("/project add <name>", "Create a new project"),
    ("/project list", "List all projects"),
    ("/project switch <#>", "Switch to a project by index"),
    ("/project remove <#>", "Remove a project by index"),
    ("/skill add <text>", "Add a project skill"),
    ("/skill list", "Show current skills"),
    ("/skill remove <#>", "Remove a skill by index"),
    ("/token", "Show current token status"),
    ("/token set <token>", "Set developer token"),
    ("/token clear", "Clear developer token"),
    ("/model", "Show current model info"),
    ("/help", "Show this help"),
]
