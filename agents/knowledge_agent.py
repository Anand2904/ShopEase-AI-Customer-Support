
import re
from pathlib import Path

from autogen_agentchat.agents import AssistantAgent


# Locate the company's knowledge base folder
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"


# 1. Search the company documents
def search_kb(query: str) -> str:
    """
    Search company policy documents and return
    relevant passages with their source filenames.
    """

    if not query.strip():
        return "No search query was provided."

    stop_words = {
        "the", "is", "a", "an", "and", "or", "to",
        "for", "of", "in", "my", "i", "can", "how",
        "what", "do", "does", "it", "me", "your",
        "was", "were", "are", "have", "has", "with"
    }

    words = set(
        word.lower()
        for word in re.findall(r"[a-zA-Z0-9]+", query)
        if word.lower() not in stop_words
    )

    if not words:
        return "No meaningful search terms were found."

    results = []

    # Read all Markdown documents
    for file_path in KNOWLEDGE_BASE_DIR.glob("*.md"):

        content = file_path.read_text(encoding="utf-8")

        # Split documents into paragraphs
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", content)
            if paragraph.strip()
        ]

        for paragraph in paragraphs:

            paragraph_words = set(
                word.lower()
                for word in re.findall(r"[a-zA-Z0-9]+", paragraph)
            )

            score = len(words.intersection(paragraph_words))

            if score > 0:
                results.append({
                    "source": file_path.name,
                    "score": score,
                    "passage": paragraph
                })

    # Return the highest matching passages
    results.sort(key=lambda item: item["score"], reverse=True)

    if not results:
        return "NO_MATCH: No relevant information was found in the company documents."

    output = []

    for result in results[:5]:
        output.append(
            f"Source: {result['source']}\n"
            f"Matching information: {result['passage']}"
        )

    return "\n\n".join(output)


# 2. Create the Knowledge Base Agent
def create_knowledge_agent(model_client):

    knowledge_agent = AssistantAgent(
        name="Knowledge_Base_Agent",

        model_client=model_client,

        description=(
            "Searches ShopEase company documents "
            "and retrieves relevant policy information."
        ),

        system_message="""
        You are the Knowledge Base Agent for ShopEase.

        Your responsibility is to find relevant information
        in the company's Markdown policy documents.

        Rules:

        1. Use the search_kb tool to search company documents.
        2. Return only information retrieved from the documents.
        3. Always mention the source filename.
        4. Never invent company policies.
        5. If no relevant information is found, clearly
           report that no matching document was found.
        6. Do not generate a customer response.

        Your output must contain:
        - Matching policy information
        - Source filename
        - Whether relevant information was found
        """,

        tools=[search_kb]
    )

    return knowledge_agent
