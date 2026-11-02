from typing import Literal

from pydantic import BaseModel, Field
from autogen_agentchat.agents import AssistantAgent


class ResolutionResult(BaseModel):
    customer_response: str = Field(
        description="A polite, helpful response written for the customer"
    )

    confidence: Literal["High", "Medium", "Low"] = Field(
        description="Confidence that the response is fully supported by the retrieved company information"
    )


def create_resolution_agent(model_client):
    resolution_agent = AssistantAgent(
        name="Customer_Resolution_Agent",
        model_client=model_client,
        description=(
            "Creates customer-ready responses using information "
            "retrieved from the company knowledge base."
        ),
        system_message="""You are the Customer Resolution Agent for ShopEase.

Your responsibility is to prepare a helpful response to the customer.

Follow these rules carefully:

1. Read the customer complaint and the information returned by the Knowledge Agent.
2. Use ONLY facts contained in the retrieved company documents.
3. Never invent policies, refund promises, delivery dates, or company procedures.
4. Be polite, professional, empathetic, and easy to understand.
5. Address the customer's actual problem.
6. If no relevant information was found, honestly explain that the available company documents do not contain an answer.
7. Do not pretend that an issue has been fixed or a refund has been approved.
8. If the issue needs further investigation, explain that support follow-up is needed.
9. Set confidence to High when the retrieved information clearly answers the complaint.
10. Set confidence to Medium when the information only partially answers it.
11. Set confidence to Low when there is no relevant information or the answer is uncertain.

Return the customer response and confidence in the required structured format.""",
        output_content_type=ResolutionResult
    )

    return resolution_agent