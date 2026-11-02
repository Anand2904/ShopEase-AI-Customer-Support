from pathlib import Path
from dotenv import load_dotenv
import os

from autogen_ext.models.openai import OpenAIChatCompletionClient

from agents.query_agent import create_query_agent
from agents.knowledge_agent import search_kb
from agents.resolution_agent import create_resolution_agent, ResolutionResult
from agents.log_agent import decide_escalation, save_ticket


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def create_model_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is missing. Add it to your .env file."
        )

    model_name = (
        os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        .strip()
        .strip('"')
        .strip("'")
        .strip()
    )

    if not model_name:
        model_name = "gpt-4o-mini"

    return OpenAIChatCompletionClient(
        model=model_name,
        api_key=api_key,
    )


async def process_ticket(
    complaint: str,
    customer_name: str = "",
    order_id: str = "",
):
    model_client = create_model_client()

    try:
        # STEP 1: Query Agent
        query_agent = create_query_agent(model_client)

        query_result = await query_agent.run(
            task=f"Analyze this customer complaint:\n{complaint}"
        )

        analysis = query_result.messages[-1].content

        # STEP 2: Knowledge Agent search
        kb_result = search_kb(
            f"{complaint} {analysis.model_dump_json()}"
        )

        knowledge_found = (
            "NO_MATCH:" not in kb_result
            and "No meaningful search terms" not in kb_result
        )

        # STEP 3: Resolution Agent
        resolution_agent = create_resolution_agent(model_client)

        resolution_task = f"""
        Customer complaint:
        {complaint}

        Query analysis:
        {analysis.model_dump_json()}

        Retrieved company information:
        {kb_result}

        Write a customer-ready response using only the retrieved information.
        """

        resolution_result = await resolution_agent.run(
            task=resolution_task
        )

        resolution = resolution_result.messages[-1].content

        if not isinstance(resolution, ResolutionResult):
            raise TypeError(
                "The Resolution Agent did not return the expected structured result."
            )

        # STEP 4: Log Agent
        sources = []

        for line in kb_result.splitlines():
            if line.startswith("Source: "):
                source = line.replace("Source: ", "").strip()
                if source not in sources:
                    sources.append(source)

        status, escalation_reason = decide_escalation(
            urgency=analysis.urgency,
            sentiment=analysis.sentiment,
            knowledge_found=knowledge_found,
            confidence=resolution.confidence,
            complaint=complaint,
        )

        ticket = save_ticket(
            customer_name=customer_name,
            order_id=order_id,
            complaint=complaint,
            category=analysis.category,
            urgency=analysis.urgency,
            sentiment=analysis.sentiment,
            kb_sources=", ".join(sources),
            response=resolution.customer_response,
            status=status,
            escalation_reason=escalation_reason,
        )

        return {
            "analysis": analysis,
            "knowledge": kb_result,
            "resolution": resolution,
            "ticket": ticket,
        }

    finally:
        await model_client.close()