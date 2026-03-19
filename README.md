# PROJECT_AGENTIC_BI 🤖📊

### "Text-to-Insights" Agentic Workflow
An advanced BI Agent that translates natural language queries into interactive Plotly visualizations using a decoupled logic architecture.

---

## 🏗️ The Architecture
Unlike standard LLM wrappers, this project utilizes **Decoupled Logic Routing**:
* **Orchestrator:** n8n (Self-hosted via Docker) acts as the logic gate.
* **Engine:** Google Gemini 2.5 Flash (Generates Plotly JSON blueprints).
* **Data Processor:** Local Python/Pandas (Handles all math/filtering to ensure 100% accuracy and data privacy).
* **Frontend:** Streamlit.



## 🌟 Key Features
* **Dual-Axis Plotly Visuals:** Supports complex clustered columns with dynamic average overlays.
* **Free-Tier Guardrails:** Built-in 12-second traffic-light cooldown to manage API rate limits.
* **Context-Aware:** Conversational memory for follow-up data exploration.

## 📖 Deep Dive & Case Study
> **[Link to Notion Portfolio Placeholder]**
*(Full breakdown of the 'Why' behind this architecture and the BI problems it solves)*

## 🛠️ Local Setup
1. Clone the repo.
2. Spin up the n8n Docker container on port 5678.
3. Import `n8n_workflow.json`.
4. Run `streamlit run app.py`.
