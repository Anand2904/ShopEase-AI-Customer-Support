# 🛍️ ShopEase – AI Customer Support Automation

An AI-powered customer support automation platform built using **Python, Microsoft AutoGen, OpenAI, and Streamlit**.

## Project Overview

ShopEase demonstrates how multiple specialized AI agents can collaborate to process e-commerce customer complaints, retrieve relevant policies, generate responses, and escalate cases requiring human attention.

## Key Features

- Customer login and personalized order history
- AI-powered customer support assistant
- Complaint registration with optional image uploads
- Multi-agent complaint processing
- Automated ticket creation and escalation
- Customer complaint tracking
- Support Staff Dashboard
- Interactive analytics and visualizations
- Docker-based application setup

## Multi-Agent Architecture

1. **Query Agent:** Classifies customer complaints, sentiment, and urgency.
2. **Knowledge Agent:** Retrieves relevant company policies.
3. **Resolution Agent:** Generates knowledge-grounded responses.
4. **Log Agent:** Records tickets and determines escalation.

## Technology Stack

- Python
- Microsoft AutoGen
- OpenAI API
- Streamlit
- SQLite
- Pandas
- Altair
- Docker

## Run Locally with Docker

Clone the repository and enter the project directory.

Create a `.env` file using `.env.example` as a reference.

Configure your own OpenAI API key and support-staff password.

Build the image:

```bash
docker build -t shopease-ai-support .
```

Start the application:

```bash
docker run --rm -p 127.0.0.1:8501:8501 --env-file .env shopease-ai-support
```

Open `http://localhost:8501` in your browser.

## Project Status

**Local demonstration / educational project.**

The current application uses demo authentication and local CSV/SQLite storage. It is not intended for unrestricted public deployment without additional security and persistent storage improvements.

## Future Improvements

- Production-ready authentication and authorization
- Persistent database storage
- Automated notifications
- Advanced ticket analytics
- AI-powered image analysis

## Disclaimer

ShopEase is an educational demonstration and is not affiliated with an actual e-commerce business.