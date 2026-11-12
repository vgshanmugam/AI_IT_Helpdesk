import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env file
load_dotenv()

GEMINI_MODEL = "gemini-2.5-flash"


def generate_ai_response(user_query: str, rag_output: dict, category: str, priority: str) -> str:
    """
    Generates a grounded, step-by-step IT support troubleshooting response
    using Gemini LLM and retrieved RAG documents.
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key or api_key == "un_copied_api_key_inga_paste_pannu":
        return (
            "⚠️ **Gemini API Key not configured.** "
            "Please add your `GEMINI_API_KEY` inside the `.env` file to enable AI-generated responses."
        )

    try:
        # Use v1beta api_version so system_instruction works across all google-genai versions
        client = genai.Client(
            api_key=api_key,
            http_options={"api_version": "v1beta"}
        )

        if rag_output["found"]:
            context_block = rag_output["context"]
            system_instruction = (
                "You are an expert, polite Enterprise IT Service Desk Assistant. "
                "Your job is to help employees resolve their IT issues using ONLY the provided "
                "Knowledge Base Context. "
                "Rules:\n"
                "1. Provide a brief, empathetic opening acknowledging the issue.\n"
                "2. Give clear, numbered, step-by-step troubleshooting instructions tailored to the user's query.\n"
                "3. Do NOT invent steps or policies not supported by the Knowledge Base Context.\n"
                "4. End by letting the user know a support ticket has been logged if the steps do not resolve the issue."
            )
            prompt = (
                f"Employee Issue: {user_query}\n"
                f"Detected Category: {category} | Priority: {priority}\n\n"
                f"Retrieved Knowledge Base Context:\n{context_block}\n\n"
                "Generate a helpful IT support troubleshooting response:"
            )
        else:
            system_instruction = (
                "You are an expert, polite Enterprise IT Service Desk Assistant. "
                "No exact troubleshooting guide was found in the internal Knowledge Base for this issue. "
                "Acknowledge the employee's problem clearly, state that no automated self-service fix is available "
                "in the knowledge base, confirm that their support ticket has been escalated to the IT engineering team, "
                "and advise them not to attempt risky hardware/system changes in the meantime."
            )
            prompt = (
                f"Employee Issue: {user_query}\n"
                f"Detected Category: {category} | Priority: {priority}\n\n"
                "Generate a helpful escalation response:"
            )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            ),
        )

        if response and response.text:
            return response.text.strip()
        return "⚠️ AI model returned an empty response. Please refer to the Knowledge Base steps below."

    except Exception as e:
        return f"⚠️ **LLM Generation Error:** `{str(e)}`\n\nPlease check your API key/internet connection or refer to the retrieved Knowledge Base steps below."