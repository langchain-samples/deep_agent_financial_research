"""Run the financial research agent against the LangSmith eval dataset.

Usage:
    python -m evals.run_evals                      # public split
    python -m evals.run_evals --splits public snowflake
    python -m evals.run_evals --skip-judge --max-concurrency 1
"""

import argparse
import asyncio
from typing import Any, Dict

from langchain_core.messages import ToolMessage
from langsmith import Client, aevaluate

from finance_research_agent.config import AgentConfig
from finance_research_agent.orchestrator import DeepResearchOrchestrator, get_subagent_calls

from .dataset import ensure_dataset
from .evaluators import CODE_EVALUATORS, make_groundedness_judge

MAX_CONTEXT_CHARS = 40_000


async def target(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Run one research request and return outputs in the shape evaluators expect."""
    orchestrator = DeepResearchOrchestrator(AgentConfig.from_env())
    result = await orchestrator.aexecute_research(inputs["query"], inputs.get("ticker"))

    state = result["state"]
    messages = state["messages"]
    structured = state["structured_response"]
    context = "\n\n".join(
        str(m.content) for m in messages if isinstance(m, ToolMessage)
    )[:MAX_CONTEXT_CHARS]

    return {
        "report": structured.model_dump() if structured else None,
        "subagents_used": sorted(set(get_subagent_calls(messages))),
        "context": context,
        "errors": result["execution_summary"]["errors"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--splits", nargs="+", default=["public"], help="Dataset splits to run")
    parser.add_argument("--experiment-prefix", default="finance-research-agent")
    parser.add_argument("--max-concurrency", type=int, default=2)
    parser.add_argument("--skip-judge", action="store_true", help="Run code evaluators only")
    args = parser.parse_args()

    config = AgentConfig.from_env()
    if "snowflake" in args.splits and not config.snowflake.enabled:
        parser.error("The snowflake split needs SNOWFLAKE_MCP_URL and SNOWFLAKE_PAT (or stdio config) set")

    client = Client()
    dataset_name = ensure_dataset(client)
    evaluators = list(CODE_EVALUATORS)
    if not args.skip_judge:
        evaluators.append(make_groundedness_judge())

    results = await aevaluate(
        target,
        data=client.list_examples(dataset_name=dataset_name, splits=args.splits),
        evaluators=evaluators,
        experiment_prefix=args.experiment_prefix,
        max_concurrency=args.max_concurrency,
        metadata={
            "model_provider": config.model.provider,
            "model": config.model.model,
            "splits": args.splits,
        },
        client=client,
    )
    print(f"Experiment: {results.experiment_name}")


if __name__ == "__main__":
    asyncio.run(main())
