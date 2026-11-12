import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rag import retrieve_information
from mcp_server import (
    create_ticket,
    get_ticket_status,
    search_tickets,
    update_ticket_status,
)

load_dotenv()

GEMINI_MODEL = "gemini-2.5-flash"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_SERVER_SCRIPT = os.path.join(BASE_DIR, "mcp_server.py")


def _get_gemini_tools() -> list:
    """Declares the 4 MCP Server tools for Gemini Function Calling."""
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="create_ticket",
                    description="Create a new IT support ticket in the helpdesk database.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "issue": types.Schema(type="STRING", description="Detailed description of the employee's IT problem."),
                            "category": types.Schema(type="STRING", description="Issue category (Network, Email, Access/Login, Hardware, Software, General IT)."),
                            "priority": types.Schema(type="STRING", description="Ticket priority (High, Medium, Low)."),
                        },
                        required=["issue", "category", "priority"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="get_ticket_status",
                    description="Retrieve the current status and details of a specific IT support ticket by its Ticket ID (e.g., 'HD-0013' or '13').",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "ticket_id": types.Schema(type="STRING", description="The ticket identifier such as 'HD-0013' or '13'."),
                        },
                        required=["ticket_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="search_tickets",
                    description="Search existing IT support tickets by issue keyword, category, or status.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "keyword": types.Schema(type="STRING", description="Optional keyword to match inside the issue description."),
                            "category": types.Schema(type="STRING", description="Optional category filter (Network, Email, Access/Login, Hardware, Software, General IT)."),
                            "status": types.Schema(type="STRING", description="Optional status filter (Open, In Progress, Resolved, Closed)."),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="update_ticket_status",
                    description="Update the status of an existing IT support ticket.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "ticket_id": types.Schema(type="STRING", description="The ticket identifier such as 'HD-0013' or '13'."),
                            "new_status": types.Schema(type="STRING", description="Target status ('Open', 'In Progress', 'Resolved', or 'Closed')."),
                        },
                        required=["ticket_id", "new_status"],
                    ),
                ),
            ]
        )
    ]


def _local_mcp_tool_dispatch(name: str, args: dict) -> str:
    """Direct fallback dispatcher invoking the MCP tool functions if stdio transport fails."""
    if name == "create_ticket":
        return create_ticket(
            issue=args.get("issue", ""),
            category=args.get("category", "General IT"),
            priority=args.get("priority", "Medium"),
        )
    elif name == "get_ticket_status":
        return get_ticket_status(ticket_id=args.get("ticket_id", ""))
    elif name == "search_tickets":
        return search_tickets(
            keyword=args.get("keyword", ""),
            category=args.get("category", ""),
            status=args.get("status", ""),
        )
    elif name == "update_ticket_status":
        return update_ticket_status(
            ticket_id=args.get("ticket_id", ""),
            new_status=args.get("new_status", "Open"),
        )
    return json.dumps({"success": False, "error": f"Unknown tool: {name}"})


async def _execute_agent_loop(call_tool_fn, transport_mode: str, user_query: str, detected_category: str, detected_priority: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    rag_output = retrieve_information(user_query, top_k=2)

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta"}
    )

    system_instruction = (
        "You are an Autonomous Enterprise IT Service Desk AI Agent connected to an MCP Server.\n"
        "You have access to 4 MCP tools: `create_ticket`, `get_ticket_status`, `search_tickets`, and `update_ticket_status`.\n\n"
        "Decision Rules:\n"
        "1. TICKET MANAGEMENT QUERIES: If the user asks to check a ticket's status, search existing tickets, "
        "or update/close/resolve a ticket, call the appropriate MCP tool (`get_ticket_status`, `search_tickets`, or `update_ticket_status`). "
        "Do NOT create a duplicate ticket for status/search/update requests.\n"
        "2. NEW IT ISSUE / TROUBLESHOOTING QUERIES: If the user describes a new technical problem:\n"
        "   - First call the `create_ticket` MCP tool using the detected category and priority so the issue is logged.\n"
        "   - Then provide a polite, clear, step-by-step troubleshooting solution strictly grounded in the Retrieved Knowledge Base Context.\n"
        "   - If the Knowledge Base Context says no relevant information was found, inform the user clearly that no self-service fix "
        "is available in the KB and share their newly created Ticket ID for IT engineering follow-up.\n"
        "3. Always include the exact Ticket ID (e.g., HD-0014) in your final response whenever a ticket is created, checked, or updated."
    )

    kb_section = (
        rag_output["context"]
        if rag_output["found"]
        else "No relevant troubleshooting document found in the Knowledge Base."
    )

    initial_user_prompt = (
        f"User Message: {user_query}\n"
        f"Pre-classified Category: {detected_category} | Pre-classified Priority: {detected_priority}\n\n"
        f"Retrieved Knowledge Base Context (Semantic RAG):\n{kb_section}"
    )

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=initial_user_prompt)]
        )
    ]

    gemini_tools = _get_gemini_tools()
    tool_logs = []
    created_ticket = None

    for _ in range(4):
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=gemini_tools,
                temperature=0.2,
            ),
        )

        candidate = response.candidates[0]
        contents.append(candidate.content)

        function_calls = [
            part.function_call
            for part in candidate.content.parts
            if part.function_call
        ]

        if not function_calls:
            final_text = "".join(
                part.text for part in candidate.content.parts if part.text
            ).strip()
            return {
                "final_response": final_text,
                "rag_output": rag_output,
                "tool_logs": tool_logs,
                "created_ticket": created_ticket,
                "transport": transport_mode,
            }

        function_response_parts = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}

            raw_output = await call_tool_fn(tool_name, tool_args)

            try:
                parsed_output = json.loads(raw_output)
            except Exception:
                parsed_output = {"raw": str(raw_output)}

            if tool_name == "create_ticket" and isinstance(parsed_output, dict) and parsed_output.get("success"):
                created_ticket = parsed_output

            tool_logs.append({
                "tool_name": tool_name,
                "arguments": tool_args,
                "output": parsed_output,
                "transport": transport_mode,
            })

            function_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response={"result": parsed_output}
                )
            )

        contents.append(
            types.Content(
                role="user",
                parts=function_response_parts
            )
        )

    return {
        "final_response": "⚠️ Agent reached maximum reasoning steps without a final answer.",
        "rag_output": rag_output,
        "tool_logs": tool_logs,
        "created_ticket": created_ticket,
        "transport": transport_mode,
    }


async def _run_agent_async(user_query: str, detected_category: str, detected_priority: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "final_response": "⚠️ `GEMINI_API_KEY` missing in `.env` file.",
            "rag_output": {"found": False, "best_score": 0.0, "results": [], "context": ""},
            "tool_logs": [],
            "created_ticket": None,
            "transport": "none",
        }

    # Connect to MCP Server via stdio transport
    try:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[MCP_SERVER_SCRIPT],
            env=os.environ.copy()
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                async def stdio_caller(name: str, args: dict) -> str:
                    res = await session.call_tool(name, arguments=args)
                    if res.content:
                        return "\n".join(c.text for c in res.content if hasattr(c, "text"))
                    return "{}"

                return await _execute_agent_loop(
                    stdio_caller, "MCP stdio", user_query, detected_category, detected_priority
                )
    except Exception:
        async def direct_caller(name: str, args: dict) -> str:
            return _local_mcp_tool_dispatch(name, args)

        return await _execute_agent_loop(
            direct_caller, "MCP in-process", user_query, detected_category, detected_priority
        )


def run_helpdesk_agent(user_query: str, detected_category: str, detected_priority: str) -> dict:
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.run(_run_agent_async(user_query, detected_category, detected_priority))