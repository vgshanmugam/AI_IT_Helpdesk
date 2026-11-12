import streamlit as st
import pandas as pd

from database import create_table, get_all_tickets, update_ticket_status
from agent import run_helpdesk_agent


# PAGE CONFIGURATION
st.set_page_config(
    page_title="AI IT Helpdesk",
    page_icon="🤖",
    layout="wide"
)

# INITIALIZE DATABASE
create_table()


# PROJECT TITLE
st.title("🤖 AI-Powered Intelligent IT Service Desk")
st.subheader("Generative AI + Semantic RAG + Autonomous AI Agent + MCP + SLA Analytics")

st.sidebar.title("Helpdesk Menu")

menu = st.sidebar.selectbox(
    "Choose a page",
    ["Chatbot", "Ticket Dashboard", "About Project"]
)


# ISSUE & PRIORITY CLASSIFICATION FUNCTION
def classify_issue(issue):

    issue_lower = issue.lower()

    if any(word in issue_lower for word in [
        "wifi", "wi-fi", "network", "internet", "vpn"
    ]):
        category = "Network"

    elif any(word in issue_lower for word in [
        "email", "outlook", "mail"
    ]):
        category = "Email"

    elif any(word in issue_lower for word in [
        "password", "login", "account", "sign in", "locked"
    ]):
        category = "Access/Login"

    elif any(word in issue_lower for word in [
        "laptop", "keyboard", "mouse", "hardware", "printer", "screen", "display"
    ]):
        category = "Hardware"

    elif any(word in issue_lower for word in [
        "software", "application", "app", "slow", "freeze", "crash"
    ]):
        category = "Software"

    else:
        category = "General IT"

    # 3-TIER PRIORITY CLASSIFICATION (High = 2h SLA, Medium = 8h SLA, Low = 24h SLA)
    if any(word in issue_lower for word in [
        "urgent", "critical", "down", "all users", "outage", "security", "blocked"
    ]):
        priority = "High"
    elif any(word in issue_lower for word in [
        "minor", "low", "how to", "question", "request", "later", "info"
    ]):
        priority = "Low"
    else:
        priority = "Medium"

    return category, priority


# CHATBOT PAGE
if menu == "Chatbot":

    st.header("💬 Autonomous IT Support Agent")

    st.write(
        "Describe a new IT issue to get AI-powered troubleshooting & automatic SLA ticket logging, "
        "or ask the Agent to **check ticket status**, **search tickets**, or **update/resolve a ticket**."
    )

    user_query = st.text_area(
        "Enter your message or IT issue:",
        placeholder=(
            "Examples:\n"
            "• Urgent: Corporate VPN is completely down for all users!\n"
            "• What is the status of ticket HD-0013?\n"
            "• Show all open Network tickets\n"
            "• Mark ticket HD-0013 as Resolved"
        ),
        height=110
    )

    if st.button("Ask AI Helpdesk Agent"):

        if user_query.strip():

            with st.spinner("AI Agent reasoning, connecting to MCP Server, and searching Knowledge Base..."):
                category, priority = classify_issue(user_query)
                agent_result = run_helpdesk_agent(
                    user_query=user_query,
                    detected_category=category,
                    detected_priority=priority
                )

            rag_output = agent_result["rag_output"]
            tool_logs = agent_result["tool_logs"]
            created_ticket = agent_result["created_ticket"]

            if created_ticket:
                st.success(
                    f"MCP Tool `create_ticket` logged **{created_ticket['ticket_id']}** "
                    f"(SLA Target: **{created_ticket.get('sla_hours', 8)} Hours** | Due: `{created_ticket.get('sla_due_at', '-')}`)!"
                )
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Ticket ID", created_ticket["ticket_id"])
                col2.metric("Category", created_ticket["category"])
                col3.metric("Priority (SLA)", f"{created_ticket['priority']} ({created_ticket.get('sla_hours', 8)}h)")
                col4.metric("RAG Confidence", f"{rag_output['best_score']:.2f}")

            st.subheader("🧠 AI Agent Response")
            st.markdown(agent_result["final_response"])

            st.subheader("🛠️ MCP Server Tool Execution Trace")
            if tool_logs:
                for idx, log in enumerate(tool_logs, start=1):
                    with st.expander(
                        f"MCP Tool Call #{idx}: `{log['tool_name']}`",
                        expanded=True
                    ):
                        st.markdown("**Arguments Passed by AI Agent:**")
                        st.json(log["arguments"])
                        st.markdown("**Response Returned by MCP Server:**")
                        st.json(log["output"])
            else:
                st.info("No MCP database tool was required for this query.")

            if created_ticket or rag_output["found"]:
                st.subheader("📚 Retrieved Knowledge Base Sources (Semantic RAG)")
                if rag_output["found"]:
                    for idx, item in enumerate(rag_output["results"], start=1):
                        with st.expander(
                            f"Source #{idx}: {item['title']} (Similarity Score: {item['score']})",
                            expanded=False
                        ):
                            st.write(item["content"])
                else:
                    st.info(
                        f"No matching troubleshooting document found "
                        f"(Highest Similarity Score: {rag_output['best_score']})."
                    )

        else:
            st.warning("Please enter your IT problem or ticket command.")


# TICKET DASHBOARD & ANALYTICS PAGE
elif menu == "Ticket Dashboard":

    st.header("🎫 IT Service Desk Admin Dashboard & SLA Analytics")

    tickets = get_all_tickets()

    if tickets:

        df = pd.DataFrame(
            tickets,
            columns=[
                "Raw ID",
                "Issue",
                "Category",
                "Priority",
                "Status",
                "Created At",
                "SLA Target",
                "SLA Due At",
                "SLA Status"
            ]
        )

        # TOP KPI METRICS
        total_tickets = len(df)
        open_tickets = len(df[df["Status"].isin(["Open", "In Progress"])])
        resolved_tickets = len(df[df["Status"].isin(["Resolved", "Closed"])])
        high_priority_open = len(df[(df["Priority"] == "High") & (df["Status"].isin(["Open", "In Progress"]))])
        sla_breached = len(df[df["SLA Status"] == "Breached"])

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Tickets", total_tickets)
        col2.metric("Active Tickets", open_tickets)
        col3.metric("Resolved / Closed", resolved_tickets)
        col4.metric("High Priority Active", high_priority_open)
        col5.metric("SLA Breached", sla_breached)

        st.divider()

        # ANALYTICS CHARTS SECTION
        st.subheader("📊 Service Desk Analytics")
        chart_col1, chart_col2, chart_col3 = st.columns(3)

        with chart_col1:
            st.markdown("**Tickets by Category**")
            cat_counts = df["Category"].value_counts()
            st.bar_chart(cat_counts)

        with chart_col2:
            st.markdown("**Tickets by Priority**")
            prio_counts = df["Priority"].value_counts()
            st.bar_chart(prio_counts)

        with chart_col3:
            st.markdown("**SLA Compliance Overview**")
            sla_counts = df["SLA Status"].value_counts()
            st.bar_chart(sla_counts)

        st.divider()

        # ADMIN QUICK STATUS UPDATE
        st.subheader("⚡ Quick Ticket Status Update")
        upd_col1, upd_col2, upd_col3 = st.columns([2, 2, 1])

        ticket_options = {
            f"HD-{row['Raw ID']:04d} [{row['Status']}] — {row['Issue'][:42]}...": row["Raw ID"]
            for _, row in df.iterrows()
        }

        with upd_col1:
            selected_label = st.selectbox("Select Ticket:", list(ticket_options.keys()))
        with upd_col2:
            new_status = st.selectbox("New Status:", ["Open", "In Progress", "Resolved", "Closed"])
        with upd_col3:
            st.write("")
            st.write("")
            if st.button("Update Status"):
                ok, msg = update_ticket_status(ticket_options[selected_label], new_status)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        st.divider()

        # FILTER & DISPLAY ALL TICKETS
        st.subheader("📋 Ticket Queue & SLA Tracking")
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            cat_filter = st.selectbox("Filter by Category", ["All"] + sorted(df["Category"].unique().tolist()))
        with f_col2:
            prio_filter = st.selectbox("Filter by Priority", ["All", "High", "Medium", "Low"])
        with f_col3:
            status_filter = st.selectbox("Filter by Status", ["All", "Open", "In Progress", "Resolved", "Closed"])

        filtered_df = df.copy()
        if cat_filter != "All":
            filtered_df = filtered_df[filtered_df["Category"] == cat_filter]
        if prio_filter != "All":
            filtered_df = filtered_df[filtered_df["Priority"] == prio_filter]
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df["Status"] == status_filter]

        display_df = filtered_df.copy()
        display_df["Ticket ID"] = display_df["Raw ID"].apply(lambda x: f"HD-{x:04d}")
        display_df = display_df[[
            "Ticket ID", "Issue", "Category", "Priority",
            "Status", "SLA Target", "SLA Due At", "SLA Status"
        ]]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info("No tickets available yet.")


# ABOUT PROJECT PAGE
elif menu == "About Project":

    st.header("📘 About Our Project")

    st.write("""
    ### Project Title

    AI-Powered Intelligent IT Service Desk Using RAG, AI Agents, and MCP

    ### End-to-End Architecture

    1. **Semantic RAG (`rag.py`)**: `sentence-transformers/all-MiniLM-L6-v2` embeddings with cosine similarity retrieval and Top-K context ranking.
    2. **Autonomous AI Agent (`agent.py`)**: Google Gemini (`gemini-2.5-flash`) agent reasoning over user intent and invoking MCP tools dynamically.
    3. **MCP Server (`mcp_server.py`)**: Standardized Model Context Protocol (`MCPServer`) exposing `create_ticket`, `get_ticket_status`, `search_tickets`, and `update_ticket_status`.
    4. **ITSM & SLA Engine (`database.py`)**: SQLite database with automated priority-based SLA tracking (`High`: 2h, `Medium`: 8h, `Low`: 24h) and live compliance monitoring.
    5. **Admin Analytics Dashboard (`app.py`)**: Real-time charts for category volume, priority distribution, SLA status, and quick ticket lifecycle management.
    """)