"""Main entry point for the financial research agent."""

import argparse
import sys
import os
from typing import Optional

from .orchestrator import DeepResearchOrchestrator
from .config import AgentConfig, OutputConfig
from .output import save_report
from .utils.validators import validate_ticker, normalize_ticker


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Financial Deep Research Agent - Comprehensive financial research using AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "ticker",
        type=str,
        help="Stock ticker symbol to research (e.g., AAPL, MSFT)",
    )
    
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Custom research query (optional)",
    )
    
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["excel", "pdf", "markdown", "json", "all"],
        default="excel",
        help="Output format for the report (default: excel)",
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for reports (default: from config)",
    )
    
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum agent steps per run, i.e. the LangGraph recursion limit (overrides config)",
    )
    
    parser.add_argument(
        "--max-replans",
        type=int,
        default=None,
        help="Deprecated and ignored: Deep Agents replans natively",
    )
    
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Maximum tokens (overrides config)",
    )
    
    parser.add_argument(
        "--max-cost",
        type=float,
        default=None,
        help="Deprecated and ignored: use --max-tokens to bound spend",
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Validate ticker
    ticker = normalize_ticker(args.ticker)
    if not validate_ticker(ticker):
        print(f"Error: Invalid ticker symbol: {args.ticker}")
        sys.exit(1)
    
    # Load configuration
    config = AgentConfig.from_env()
    
    # Override config with command-line arguments
    if args.max_iterations:
        config.execution.max_iterations = args.max_iterations
    if args.max_replans:
        config.execution.max_replans = args.max_replans
    if args.max_tokens:
        config.budget.max_tokens = args.max_tokens
    if args.max_cost:
        config.budget.max_cost = args.max_cost
    if args.output_dir:
        config.output.output_dir = args.output_dir
    
    # Create research query
    if args.query:
        user_query = args.query
    else:
        user_query = f"Perform comprehensive financial research on {ticker}. Include stock information, financial statements, SEC filings, news analysis, risk assessment, and generate a detailed research report."
    
    if args.verbose:
        print(f"Starting research for {ticker}...")
        print(f"Query: {user_query}")
        print(f"Configuration:")
        print(f"  Max iterations: {config.execution.max_iterations}")
        print(f"  Max tokens: {config.budget.max_tokens}")
        print(f"  Max time: {config.budget.max_time_minutes} min")
        print(f"  Snowflake: {'enabled' if config.snowflake.enabled else 'not configured'}")
        print()
    
    # Create orchestrator
    orchestrator = DeepResearchOrchestrator(config)
    
    # Execute research
    try:
        result = orchestrator.execute_research(user_query, ticker)
        
        if args.verbose:
            print("Research execution completed.")
            print(f"Status: {result['status']}")
            summary = result["execution_summary"]
            print(f"Model turns: {summary['iterations']}")
            print(f"Subagent calls: {summary['subagent_calls']} "
                  f"({', '.join(result['verification']['subagents_used']) or 'none'})")
            print(f"Tokens used: {summary['tokens_used']}")
            print(f"Time elapsed: {summary['time_elapsed']:.2f}s")
            for error in summary["errors"]:
                print(f"  Error: {error}")
            print()
        
        # Generate and save report
        report = result.get("state", {}).get("report")
        if report:
            # Determine output formats
            if args.output_format == "all":
                formats = ["excel", "pdf", "markdown", "json"]
            else:
                formats = [args.output_format]
            
            # Save report
            saved_files = save_report(report, ticker, formats, config.output)
            
            print("Report generated successfully!")
            print(f"Output directory: {saved_files['output_dir']}")
            for format, path in saved_files["formats"].items():
                if isinstance(path, dict) and "error" in path:
                    print(f"  {format}: Error - {path['error']}")
                else:
                    print(f"  {format}: {path}")
        else:
            print("Warning: No report was generated.")
            if args.verbose:
                print("Verification results:")
                verification = result.get("verification", {})
                print(f"  Completeness: {verification.get('overall_completeness', 0):.1f}%")
                print(f"  Is complete: {verification.get('is_complete', False)}")
        
        # Exit with appropriate code
        if result["status"] == "completed":
            sys.exit(0)
        else:
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nResearch interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"Error during research execution: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
