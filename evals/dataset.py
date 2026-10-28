"""Evaluation dataset for the financial research agent.

Reference outputs describe expected *behavior* (which subagents to use, what the report
must mention) rather than exact figures, since market data changes daily.
"""

from typing import Any, Dict, List

from langsmith import Client

DATASET_NAME = "finance-research-agent"

# split "public": answerable from public market data only
# split "snowflake": requires the snowflake_analyst subagent and a configured Snowflake MCP server
EXAMPLES: List[Dict[str, Any]] = [
    {
        "inputs": {
            "ticker": "AAPL",
            "query": "Perform comprehensive financial research on AAPL. Include valuation "
            "metrics, financial statements, recent news, and key risks.",
        },
        "outputs": {
            "expected_subagents": ["data_collector", "analyst"],
            "must_mention": [["AAPL", "Apple"]],
        },
        "split": "public",
    },
    {
        "inputs": {
            "ticker": "MSFT",
            "query": "Compare MSFT with GOOGL on profitability, growth, and valuation. "
            "Which looks more attractively valued?",
        },
        "outputs": {
            "expected_subagents": ["data_collector", "analyst"],
            "must_mention": [["MSFT", "Microsoft"], ["GOOGL", "Alphabet", "Google"]],
        },
        "split": "public",
    },
    {
        "inputs": {
            "ticker": "JPM",
            "query": "Assess the risk profile of JPM: leverage, credit exposure, and "
            "volatility. Flag the top three risks.",
        },
        "outputs": {
            "expected_subagents": ["data_collector", "analyst"],
            "must_mention": [["JPM", "JPMorgan"]],
            "min_risks": 3,
        },
        "split": "public",
    },
    {
        "inputs": {
            "ticker": "NVDA",
            "query": "Summarize recent news and market sentiment for NVDA and how it relates "
            "to the stock's recent price trend.",
        },
        "outputs": {
            "expected_subagents": ["data_collector"],
            "must_mention": [["NVDA", "NVIDIA", "Nvidia"]],
        },
        "split": "public",
    },
    {
        "inputs": {
            "ticker": "ZZZQX",
            "query": "Perform comprehensive financial research on ZZZQX.",
        },
        "outputs": {
            "expected_subagents": ["data_collector"],
            "must_mention": [["ZZZQX"]],
            "expect_limitations": True,
        },
        "split": "public",
    },
    {
        "inputs": {
            "ticker": "BLDR",
            "query": "Compare our internal equity research coverage of BLDR (ratings, price "
            "targets, estimates) with its public market data and recent performance.",
        },
        "outputs": {
            "expected_subagents": ["snowflake_analyst", "data_collector"],
            "must_mention": [["BLDR", "Builders FirstSource"]],
            "expect_internal_data": True,
        },
        "split": "snowflake",
    },
]


def ensure_dataset(client: Client) -> str:
    """Create the dataset and seed examples if it doesn't exist yet.

    Returns:
        The dataset name
    """
    if client.has_dataset(dataset_name=DATASET_NAME):
        return DATASET_NAME

    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="Behavioral evals for the deep financial research agent",
    )
    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {"inputs": e["inputs"], "outputs": e["outputs"], "split": e["split"]}
            for e in EXAMPLES
        ],
    )
    return DATASET_NAME
