# 🤖 AI-Powered Intelligent IT Service Desk (RAG + AI Agents + MCP)

An end-to-end Intelligent IT Service Management (ITSM) Helpdesk built using **Semantic RAG**, **Google Gemini LLM**, an **Autonomous AI Agent**, and a **Model Context Protocol (MCP) Server** with real-time **SLA Tracking & Admin Analytics**.

## 🚀 Key Features
- **Semantic RAG Knowledge Retrieval (`rag.py`)**: Uses `sentence-transformers/all-MiniLM-L6-v2` embeddings and cosine similarity to retrieve top-K troubleshooting documents with confidence scores.
- **Grounded Generative AI (`llm.py` & `agent.py`)**: Powered by Google Gemini (`gemini-2.5-flash`) to generate accurate, context-grounded troubleshooting steps without hallucination.
- **Autonomous AI Agent + MCP Server (`mcp_server.py`)**: Exposes standardized MCP tools (`create_ticket`, `get_ticket_status`, `search_tickets`, `update_ticket_status`) invoked dynamically by the AI Agent.
- **Priority & SLA Engine (`database.py`)**: Automatic issue classification (`Network`, `Email`, `Access/Login`, `Hardware`, `Software`, `General IT`) and 3-tier SLA deadlines (`High`: 2h, `Medium`: 8h, `Low`: 24h).
- **Admin Analytics Dashboard (`app.py`)**: Interactive Streamlit UI displaying live ticket metrics, category/priority/SLA compliance charts, and status lifecycle controls.

## 🛠️ Tech Stack
- **Frontend**: Streamlit, Pandas
- **AI / ML**: Sentence Transformers (`all-MiniLM-L6-v2`), Google Gemini API (`google-genai`)
- **Agent & Protocol**: Model Context Protocol (`mcp` `MCPServer`), Function Calling
- **Database**: SQLite3

## ⚙️ Local Setup Instructions
1. **Clone the repository**
   ```bash
   git clone [https://github.com/](https://github.com/)<your-username>/AI-IT-Helpdesk-RAG-Agent-MCP.git
   cd AI-IT-Helpdesk-RAG-Agent-MCP