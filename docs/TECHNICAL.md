# Technical Guide

Setup, configuration, and internals. For the overview and architecture, see the [README](../README.md).

A comprehensive financial services deep research agent built with LangChain DeepAgents and LangGraph. This agent performs automated financial research on publicly-traded companies, gathering data from multiple sources, performing analysis, and generating detailed research reports in multiple formats.

## Features

- **Planning & Task Decomposition**: Uses DeepAgents' TodoList middleware to break down complex research into manageable steps
- **Subagent Delegation**: Specialized subagents for data collection, analysis, and reporting with context isolation
- **Filesystem Management**: Stores intermediate results and context to manage large research tasks
- **Deep Research Pattern**: Implements replanning and verification to ensure comprehensive research
- **Multiple Data Sources**: Integrates Yahoo Finance, SEC filings, news APIs, and Alpha Vantage
- **Multiple Output Formats**: Supports Excel, PDF, Markdown, and JSON outputs
- **Budget Management**: Tracks token usage, costs, and execution time
- **Error Handling**: Robust error handling and retry logic

## Architecture

The agent uses a multi-layered architecture:

1. **Main Deep Agent** (`deepagents>=0.7.32`): Plans with `write_todos`, delegates with the `task` tool, keeps working notes in an in-memory virtual filesystem, and returns a structured `ResearchReport`
2. **Specialized Subagents**:
   - **data_collector**: Public market data (Yahoo Finance, SEC filings, news)
   - **analyst**: Ratios, peer comparison, risk, and trends
   - **report_generator**: Drafts the report content
   - **snowflake_analyst** (optional): Read-only queries against your Snowflake warehouse through MCP
3. **Deep Research Orchestrator**: Runs the agent with step, time, and token budgets and tags each run for LangSmith
4. **CLI renderer**: Writes the structured report to Excel, PDF, Markdown, or JSON in `OUTPUT_DIR`

### Architecture Diagram

```
User Query → Main Deep Agent → Planning → Data Collection → Analysis → Report Generation → Verification
                ↓                    ↓            ↓              ↓              ↓
            Subagents         Yahoo Finance   SEC Filings   News APIs    Multiple Formats
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip or uv package manager

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd deep_agent_financial_research
```

2. Install the package (add `[dev]` for tests and evals):
```bash
pip install -e ".[dev]"
```

Or using uv:
```bash
uv venv && uv pip install -e ".[dev]"
```

3. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` (for LLM)
- `SEC_USER_AGENT` (your name/company and email; SEC EDGAR requires it, no key needed)
- `NEWS_API_KEY` (optional; news comes from public RSS feeds without it)
- `LANGSMITH_API_KEY` (optional, for tracing and evals)
- `SNOWFLAKE_MCP_URL` + `SNOWFLAKE_PAT` (optional, enables the snowflake_analyst subagent)

## Usage

### Basic Usage

Research a stock with default settings:

```bash
python -m src.finance_research_agent.main AAPL
```

### Command-Line Options

```bash
python -m src.finance_research_agent.main AAPL --query "Analyze Apple's financial performance and risk profile" --output-format excel --verbose
```

**Arguments:**
- `ticker`: Stock ticker symbol (required)
- `--query`: Custom research query (optional)
- `--output-format`: Output format - excel, pdf, markdown, json, or all (default: excel)
- `--output-dir`: Output directory (default: from config)
- `--max-iterations`: Maximum number of iterations (overrides config)
- `--max-replans`: Maximum number of replans (overrides config)
- `--max-tokens`: Maximum tokens (overrides config)
- `--max-cost`: Maximum cost in USD (overrides config)
- `--verbose`: Enable verbose output

### Example Queries

```bash
# Basic research
python -m src.finance_research_agent.main MSFT

# Custom query
python -m src.finance_research_agent.main TSLA --query "Analyze Tesla's revenue growth and market position"

# Multiple formats
python -m src.finance_research_agent.main GOOGL --output-format all

# With budget limits
python -m src.finance_research_agent.main AAPL --max-tokens 50000 --max-cost 0.50
```

## Configuration

### Environment Variables

The agent can be configured via environment variables in `.env`:

```env
# LLM Configuration
OPENAI_API_KEY=your_key_here
DEFAULT_MODEL=gpt-4o
DEFAULT_TEMPERATURE=0.7

# Budget Limits
MAX_TOKENS=100000
MAX_COST=1.00
MAX_TIME_MINUTES=10

# Execution Parameters
MAX_ITERATIONS=25
MAX_REPLANS=2
MAX_TASK_RETRIES=5

# Output Configuration
OUTPUT_DIR=output
DEFAULT_OUTPUT_FORMAT=excel
```

### Configuration File

Additional configuration can be set in `config/agent_config.yaml`:

```yaml
agent:
  name: "FinancialDeepResearchAgent"

model:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.7

budget:
  max_tokens: 100000
  max_cost: 1.00
  max_time_minutes: 10

execution:
  max_iterations: 25
  max_replans: 2
  enable_parallel: true
```

## Output Formats

The agent generates reports in multiple formats:

- **Excel (.xlsx)**: Structured spreadsheet with multiple sheets
- **PDF (.pdf)**: Professional document format
- **Markdown (.md)**: Human-readable markdown document
- **JSON (.json)**: Structured data format for programmatic access

Reports are saved to the `output/` directory by default, with filenames like:
`AAPL_20240101_120000.xlsx`

## Research Process

1. **Planning**: Agent creates a detailed plan using TodoList middleware
2. **Data Collection**: Data collector subagent gathers:
   - Stock information and metrics
   - Financial statements
   - SEC filings
   - News articles
3. **Analysis**: Analyst subagent performs:
   - Financial ratio calculations
   - Risk assessment
   - Trend analysis
   - Company comparisons
4. **Report Generation**: Report generator subagent creates comprehensive reports
5. **Iteration**: The agent updates its todo list as results come in and re-delegates when data is missing
6. **Structured output**: The agent returns a `ResearchReport`, which the CLI renders to files

## Data Sources

The agent integrates with multiple financial data sources:

- **Yahoo Finance** (via yfinance): Stock prices, metrics, financial statements
- **SEC EDGAR** (free public API, no key): Filing index, filing text by section, and as-reported XBRL financials. Set `SEC_USER_AGENT` per SEC's fair-access policy.
- **News** (public RSS, no key): Yahoo Finance per-ticker headlines and Google News search. Uses NewsAPI instead if `NEWS_API_KEY` is set.
- **Snowflake** (optional, via MCP): Internal or proprietary data

## Demo UI

Two ways to use the agent interactively:

**Streamlit demo app.** This has clickable sample questions, live progress (plan, subagent
delegations, tool calls), the rendered report with Markdown/Excel/PDF/JSON downloads, and a
link to each run's LangSmith trace.

```bash
streamlit run ui/app.py        # http://localhost:8501
```

**LangGraph Studio.** This shows the graph, full state, and step-by-step execution, for
technical audiences.

```bash
langgraph dev                  # opens Studio against http://127.0.0.1:2024
```

Sample questions with notes on what each one shows are in
[DEMO_QUESTIONS.md](DEMO_QUESTIONS.md).

## Snowflake MCP

The `snowflake_analyst` subagent is added automatically when Snowflake is configured. Without
configuration it is left out and the agent runs normally.

**Option A: Snowflake-managed MCP server (default, recommended)**

1. Create an MCP server in Snowflake with a read-only SQL tool (and any Cortex Analyst or
   Search tools you want):
   ```sql
   CREATE MCP SERVER analytics.finance.research_mcp FROM SPECIFICATION $$
   tools:
     - name: "sql_exec_tool"
       type: "SYSTEM_EXECUTE_SQL"
       description: "Run read-only SQL"
       config: { read_only: true, warehouse: "RESEARCH_WH" }
   $$;
   ```
2. Create a PAT for a **least-privileged role** that can only `SELECT` what the agent needs.
3. Set `SNOWFLAKE_MCP_URL=https://<account>.snowflakecomputing.com/api/v2/databases/ANALYTICS/schemas/FINANCE/mcp-servers/RESEARCH_MCP`
   and `SNOWFLAKE_PAT`. Use hyphens, not underscores, in the account hostname.

**Option B: local Snowflake-Labs server (deprecated by Snowflake)**

Set `SNOWFLAKE_MCP_TRANSPORT=stdio` plus `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
`SNOWFLAKE_PASSWORD` (a PAT), `SNOWFLAKE_ROLE`, and `SNOWFLAKE_WAREHOUSE`. The server runs via
`uvx snowflake-labs-mcp` with `config/snowflake_mcp_readonly.yaml`, which permits only
`SELECT`/`DESCRIBE`/`USE`.

**Read-only enforcement** has three layers: the role's grants, the server config
(`read_only: true` or `sql_statement_permissions`), and a client-side interceptor that
rejects anything other than a single `SELECT`/`WITH`/`SHOW`/`DESCRIBE`/`EXPLAIN` statement.

## LangSmith

**Tracing:** set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` in
`.env` (see `.env.example`). Every run, including subagent and MCP tool calls, is traced and
tagged with the ticker and model.

**Studio:** `langgraph dev` serves the agent in LangGraph Studio using `langgraph.json`.

**Evals:** `evals/` contains a behavioral dataset and evaluators:

| Evaluator | Type | Checks |
|---|---|---|
| `report_produced` | code | A structured report came back within budget |
| `report_completeness` | code | Required sections are populated |
| `delegated_to_expected_subagents` | code | The right subagents were used |
| `mentions_required_entities` | code | The report covers the requested companies |
| `metrics_cite_sources` | code | Every metric names its source |
| `handles_missing_data` | code | Flags limitations instead of inventing numbers; uses internal data when asked |
| `groundedness` | LLM judge | The report is supported by what the subagents actually returned |

```bash
python -m evals.run_evals                          # public split; creates the dataset on first run
python -m evals.run_evals --splits public snowflake
python -m evals.run_evals --skip-judge             # code evaluators only
```

The judge uses `EVAL_JUDGE_MODEL` (for example `openai:gpt-4o`) if set, otherwise the agent's
model. Results show up as experiments on the `finance-research-agent` dataset in LangSmith.

## Project Structure

```
deep_agent_financial_research/
├── src/
│   └── finance_research_agent/
│       ├── __init__.py
│       ├── main.py              # Main entry point
│       ├── agent.py              # Core deep agent
│       ├── config.py             # Configuration classes
│       ├── orchestrator.py       # Runs the agent with budgets + LangSmith metadata
│       ├── models.py             # Chat model factory
│       ├── schemas.py            # ResearchReport structured output
│       ├── subagents/            # SubAgent specs
│       │   ├── data_collector.py
│       │   ├── analyst.py
│       │   ├── report_generator.py
│       │   └── snowflake.py      # Snowflake MCP subagent + read-only SQL guard
│       ├── tools/                # Tool implementations
│       │   ├── stock_data.py
│       │   ├── sec_filings.py
│       │   ├── news.py
│       │   ├── analysis.py
│       │   └── reporting.py
│       ├── prompts/              # System prompts
│       │   ├── main_agent.md
│       │   ├── data_collector.md
│       │   ├── analyst.md
│       │   ├── report_generator.md
│       │   └── snowflake_analyst.md
│       ├── utils/                # Utility functions
│       │   ├── validators.py
│       │   ├── data_processing.py
│       │   └── formatters.py
│       └── output/               # Output management
│           └── __init__.py
├── config/
│   ├── agent_config.yaml        # Configuration file
│   └── snowflake_mcp_readonly.yaml  # Read-only config for the stdio Snowflake server
├── ui/                           # Streamlit demo app + sample questions
├── docs/DEMO_QUESTIONS.md        # Demo question guide
├── evals/                        # LangSmith dataset, evaluators, runner
├── tests/                        # Offline tests (scripted fake model, no API keys)
├── legacy/                       # Old hand-coded workflow, not imported
├── langgraph.json                # LangGraph Studio / Agent Server config
├── .env.example
├── output/                       # Generated reports (gitignored)
├── requirements.txt              # Python dependencies
├── pyproject.toml               # Project configuration
├── README.md                    # Overview, architecture, demo talk track
└── docs/TECHNICAL.md            # This file
```

## API Documentation

### Main Agent

The main agent is created using `create_main_agent()` which sets up:
- Deep Agents with planning, virtual filesystem, and subagent delegation
- Three subagents, plus `snowflake_analyst` when Snowflake tools are passed in
- `ResearchReport` structured output

Use `await build_agent(config)` to also load Snowflake MCP tools. MCP tools are async-only,
so run that agent with `ainvoke`/`astream`.

### Orchestrator

The `DeepResearchOrchestrator` class manages:
- Running the agent (`execute_research` / `aexecute_research`)
- Step (`MAX_ITERATIONS`, the LangGraph recursion limit), time, and token budgets
- LangSmith run name, tags, and metadata

### Tools

All tools are implemented as LangChain tools and can be used independently:

- **Stock Data Tools**: `get_stock_info`, `get_stock_metrics`, `get_historical_prices`, `get_financial_statements`
- **SEC Filings Tools**: `search_sec_filings`, `get_filing_content`, `get_reported_financials`
- **News Tools**: `search_financial_news`, `get_news_sentiment`, `get_market_news`
- **Analysis Tools**: `calculate_financial_ratios`, `compare_companies`, `assess_risk_profile`, `analyze_trends`
- **Reporting Tools**: `generate_excel_report`, `generate_pdf_report`, `generate_markdown_report`, `generate_json_report`

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/
ruff check src/
```

### Adding New Data Sources

1. Create a new tool in `src/finance_research_agent/tools/`
2. Add the tool to the appropriate subagent in `src/finance_research_agent/subagents/`
3. Update the configuration if needed

### Adding New Output Formats

1. Create a new generator function in `src/finance_research_agent/tools/reporting.py`
2. Add it to `REPORTING_TOOLS`
3. Update the output format validation in `src/finance_research_agent/utils/validators.py`

## Limitations

- SEC filings integration requires proper API setup and authentication
- News API integration requires API keys for full functionality
- Some data sources may have rate limits
- Report generation quality depends on the completeness of collected data

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the Apache 2.0 License.

## References

- [LangChain DeepAgents](https://github.com/langchain-ai/deepagents)
- [LangGraph Documentation](https://docs.langchain.com/langgraph)
- [The AI Alliance Deep Research Agent](https://github.com/The-AI-Alliance/deep-research-agent-for-finance)

## Support

For issues, questions, or contributions, please open an issue on GitHub.
