"""End-to-end agent tests with a scripted model (no network)."""

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from finance_research_agent.agent import create_main_agent
from finance_research_agent.orchestrator import DeepResearchOrchestrator

from .conftest import report_call, scripted_model, task_call


async def test_research_run_delegates_and_returns_report(config, use_model):
    use_model(scripted_model([
        task_call("data_collector", "Get AAPL stock info", "call-1"),
        AIMessage(content="AAPL P/E is 30x per Yahoo Finance."),  # subagent's answer
        report_call(),
    ]))

    result = await DeepResearchOrchestrator(config).aexecute_research("Research AAPL", "AAPL")

    assert result["status"] == "completed"
    assert result["verification"]["subagents_used"] == ["data_collector"]
    report = result["state"]["report"]
    assert report["metadata"]["ticker"] == "AAPL"
    assert report["stock_info"] == {"P/E": "30x (Yahoo Finance)"}
    assert result["execution_summary"]["errors"] == []


async def test_snowflake_subagent_available_when_tools_loaded(config, use_model):
    @tool
    def run_sql(sql: str) -> str:
        """Run a read-only SQL query."""
        return "QTY=100"

    use_model(scripted_model([
        task_call("snowflake_analyst", "Get AAPL position", "call-1"),
        AIMessage(content="Position: 100 shares (HOLDINGS.POSITIONS)."),
        report_call(internal_data_findings="100 shares"),
    ]))
    agent = create_main_agent(config, snowflake_tools=[run_sql])

    result = await agent.ainvoke({"messages": [{"role": "user", "content": "Our AAPL position?"}]})

    task_results = [m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "task"]
    assert "100 shares" in task_results[0].content
    assert result["structured_response"].internal_data_findings == "100 shares"


async def test_token_budget_stops_run(config, use_model):
    over_budget = task_call("data_collector", "Get data", "call-1")
    over_budget.usage_metadata = {"input_tokens": 900, "output_tokens": 200, "total_tokens": 1100}
    use_model(scripted_model([over_budget]))
    config.budget.max_tokens = 1000

    result = await DeepResearchOrchestrator(config).aexecute_research("Research AAPL", "AAPL")

    assert result["status"] == "incomplete"
    assert "Token budget exceeded" in result["execution_summary"]["errors"][0]
