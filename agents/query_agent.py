
from typing import Literal

from pydantic import BaseModel, Field
from autogen_agentchat.agents import AssistantAgent


# 1. Define the expected analysis format
class QueryAnalysis(BaseModel):
    category: Literal[
        "Shipping",
        "Refund",
        "Account",
        "Product",
        "Billing",
        "Other"
    ] = Field(description="The category of the customer complaint")

    urgency: Literal["Low", "Medium", "High"] = Field(
        description="How urgently the complaint needs attention"
    )

    sentiment: Literal[
        "Angry",
        "Frustrated",
        "Neutral",
        "Satisfied"
    ] = Field(description="The customer's emotional tone")

    summary: str = Field(
        description="A short, one-line summary of the complaint"
    )


# 2. Create the Customer Query Agent
def create_query_agent(model_client):

    query_agent = AssistantAgent(
        name="Customer_Query_Agent",

        model_client=model_client,

        description=(
            "Analyzes customer complaints and identifies "
            "their category, urgency, sentiment and summary."
        ),

        system_message="""
        You are the Customer Query Agent for ShopEase,
        an online shopping company.

        Your responsibility is to analyze customer complaints.

        Follow these rules:

        1. Identify the correct complaint category.
        2. Assign urgency as Low, Medium or High.
        3. Identify customer sentiment.
        4. Write a short, clear summary.

        Category options:
        Shipping, Refund, Account, Product, Billing, Other.

        Urgency guidelines:
        Low: General questions and routine requests.
        Medium: Problems requiring support attention.
        High: Serious complaints, major delays, repeated
        failures, payment disputes or legal threats.

        Never invent customer information.

        Return only the structured analysis requested.
        """,

        output_content_type=QueryAnalysis
    )

    return query_agent
