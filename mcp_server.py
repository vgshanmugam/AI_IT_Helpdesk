import re
import json
from mcp.server.mcpserver import MCPServer

from database import (
    create_table,
    create_ticket as db_create_ticket,
    get_ticket_by_id as db_get_ticket_by_id,
    search_tickets as db_search_tickets,
    update_ticket_status as db_update_ticket_status,
)

create_table()
mcp = MCPServer("IT-Helpdesk-MCP-Server")


def _parse_ticket_number(ticket_id_str: str) -> int:
    match = re.search(r"\d+", str(ticket_id_str))
    if not match:
        raise ValueError(f"Invalid ticket ID format: '{ticket_id_str}'")
    return int(match.group())


@mcp.tool()
def create_ticket(issue: str, category: str = "General IT", priority: str = "Medium") -> str:
    """
    Create a new IT support ticket in the helpdesk database with automatic SLA tracking.
    Args:
        issue: Detailed description of the employee's IT problem.
        category: Issue category (Network, Email, Access/Login, Hardware, Software, General IT).
        priority: Ticket priority (High, Medium, Low).
    """
    ticket_num = db_create_ticket(issue=issue, category=category, priority=priority)
    created = db_get_ticket_by_id(ticket_num)
    return json.dumps({
        "success": True,
        "ticket_id": created["ticket_id"],
        "issue": created["issue"],
        "category": created["category"],
        "priority": created["priority"],
        "status": created["status"],
        "sla_hours": created["sla_hours"],
        "sla_due_at": created["sla_due_at"],
        "sla_status": created["sla_status"],
        "message": f"Support ticket {created['ticket_id']} created with {created['sla_hours']}h SLA."
    })


@mcp.tool()
def get_ticket_status(ticket_id: str) -> str:
    """
    Retrieve the current status, SLA deadline, and details of a specific IT support ticket by its Ticket ID.
    Args:
        ticket_id: The ticket identifier such as 'HD-0013' or '13'.
    """
    try:
        num_id = _parse_ticket_number(ticket_id)
    except ValueError as e:
        return json.dumps({"success": False, "error": str(e)})

    ticket = db_get_ticket_by_id(num_id)
    if not ticket:
        return json.dumps({
            "success": False,
            "error": f"Ticket HD-{num_id:04d} was not found in the database."
        })

    return json.dumps({
        "success": True,
        "ticket": ticket
    })


@mcp.tool()
def search_tickets(keyword: str = "", category: str = "", status: str = "") -> str:
    """
    Search existing IT support tickets by issue keyword, category, or status.
    Args:
        keyword: Optional keyword to match inside the issue description.
        category: Optional category filter (Network, Email, Access/Login, Hardware, Software, General IT).
        status: Optional status filter (Open, In Progress, Resolved, Closed).
    """
    matches = db_search_tickets(keyword=keyword, category=category, status=status)
    return json.dumps({
        "success": True,
        "count": len(matches),
        "tickets": matches
    })


@mcp.tool()
def update_ticket_status(ticket_id: str, new_status: str) -> str:
    """
    Update the status of an existing IT support ticket.
    Args:
        ticket_id: The ticket identifier such as 'HD-0013' or '13'.
        new_status: The target status ('Open', 'In Progress', 'Resolved', or 'Closed').
    """
    try:
        num_id = _parse_ticket_number(ticket_id)
    except ValueError as e:
        return json.dumps({"success": False, "error": str(e)})

    success, msg = db_update_ticket_status(num_id, new_status)
    return json.dumps({
        "success": success,
        "ticket_id": f"HD-{num_id:04d}",
        "new_status": new_status.strip().title(),
        "message": msg
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")