from pathlib import Path
import json
from datetime import datetime
import typer
from rich.console import Console
from rich.table import Table
from typing import Dict, List, Optional

from pipeline.retrieval.filter_builder import ElasticsearchFilterBuilder
from pipeline.retrieval.analyzer import QueryAnalyzer
from pipeline.retrieval.schema import (
    QueryAnalysis, CompanyInfo, TemporalInfo, QuarterInfo, ContentInfo
)

app = typer.Typer()
console = Console()

# Load test data paths
QA_PAIRS_PATH = Path(__file__).parent.parent.parent.parent / 'data' / 'qa_pairs.json'

def get_manual_examples() -> List[QueryAnalysis]:
    """Get manually crafted test examples"""
    examples = [
        # Shin-Etsu Chemical example
        QueryAnalysis(
            thought_process=[
                "First, I identify the main entities: Found Shin-Etsu Chemical as the primary company",
                "Then, I determine company origins: Shin-Etsu Chemical is a Japanese company",
                "Next, I analyze temporal references: 'early 2025' implies first few months",
                "Then, I identify domain and content-specific terms: Focus on share repurchase and tender offer terms",
                "Finally, I assess confidence: High confidence on company, slightly lower on temporal due to vague 'early'"
            ],
            company_info=CompanyInfo(
                name="Shin-Etsu Chemical",
                origin="Japan",
                variations=["Shin-Etsu Chemical", "信越化学工業", "シンエツ化学", "Shin Etsu Chemical Co., Ltd.", "Shin-Etsu", "shinetsu"],
                confidence=0.95
            ),
            temporal_info=TemporalInfo(
                years=[2025],
                months=[1, 2, 3, 4],
                quarter=QuarterInfo(number=1, year=2025),
                confidence=0.7
            ),
            content_info=ContentInfo(
                domain="chemicals",
                key_terms=["share repurchase", "tender offer", "自己株式取得", "公開買付け"],
                action_type="share repurchase/tender offer",
                confidence=0.9
            ),
            original_query="Summarize Shin-Etsu Chemical's actions regarding its share repurchase and tender offer in early 2025."
        ),
        # Example with missing fields
        QueryAnalysis(
            thought_process=[
                "This query doesn't have enough information to determine specific fields",
                "No clear company or temporal information found",
                "Only found some general content terms"
            ],
            company_info=CompanyInfo(
                confidence=0.2  # Low confidence, no company identified
            ),
            temporal_info=TemporalInfo(
                confidence=0.1  # Low confidence, no temporal info
            ),
            content_info=ContentInfo(
                key_terms=["earnings", "results"],
                confidence=0.6  # Only found some general terms
            ),
            original_query="Show me some recent earnings reports."
        ),
        # Sumitomo Mitsui Trust Holdings example
        QueryAnalysis(
            thought_process=[
                "First, I identify the main entities: Found Sumitomo Mitsui Trust Holdings as primary company",
                "Then, I determine company origins: Japanese financial institution",
                "Next, I analyze temporal references: 1Q FY2024 implies specific fiscal quarter",
                "Then, I identify domain and content-specific terms: Focus on financial results",
                "Finally, I assess confidence: High confidence overall but need to consider fiscal year timing"
            ],
            company_info=CompanyInfo(
                name="Sumitomo Mitsui Trust Holdings",
                origin="Japan",
                variations=["SMTH", "三井住友", "Sumitomo Mitsui", "三井住友トラスト"],
                confidence=0.95
            ),
            temporal_info=TemporalInfo(
                years=[2024],
                months=[4, 5, 6, 7],
                quarter=QuarterInfo(number=1, year=2024),
                confidence=0.9
            ),
            content_info=ContentInfo(
                domain="financial services",
                key_terms=["earnings", "決算", "results", "業績"],
                action_type="earnings announcement",
                confidence=0.9
            ),
            original_query="What financial results did Sumitomo Mitsui Trust Holdings announce for 1Q FY2024?"
        ),
        QueryAnalysis(
            thought_process=[
                "First, I identify the main entities: Found K Car as the primary company",
                "Then, I determine company origins: K Car is a Korean company",
                "Next, I analyze temporal references: Q3 2024 could span multiple months, with specific Nov 7 event date",
                "Then, I identify domain and content-specific terms: Focus on earnings call details, including Korean translations",
                "Finally, I assess confidence: High confidence but acknowledging temporal range uncertainty"
            ],
            company_info=CompanyInfo(
                name="K Car",
                origin="South Korea",
                variations=["K Car", "케이카", "KCar", "케이 카"],
                confidence=0.9
            ),
            temporal_info=TemporalInfo(
                years=[2024],
                months=[6, 7, 8, 9, 10, 11, 12],
                quarter=QuarterInfo(number=3, year=2024),
                confidence=0.8
            ),
            content_info=ContentInfo(
                domain="automotive",
                key_terms=["earnings", "실적", "call", "발표"],
                action_type="earnings call",
                confidence=0.95
            ),
            original_query="What are the details of K Car's Q3 2024 earnings call scheduled for November 7, 2024?"
        ),
        QueryAnalysis(
            thought_process=[
                "First, I identify the main entities: Samsung SDS, IT services subsidiary of Samsung Group",
                "Then, I determine company origins: Korean company, need Hangul variations",
                "Next, I analyze temporal references: Q4 2024 and specific date Jan 23, 2025",
                "Then, I identify domain and content-specific terms: Focus on earnings call and IT services",
                "Finally, I assess confidence: High confidence due to well-known company and explicit dates"
            ],
            company_info=CompanyInfo(
                name="Samsung SDS",
                origin="South Korea",
                variations=["Samsung", "삼성", "Samsung SDS", "삼성SDS"],
                confidence=0.95
            ),
            temporal_info=TemporalInfo(
                years=[2024, 2025],
                months=[10, 11, 12, 1],
                quarter=QuarterInfo(number=4, year=2024),
                confidence=0.95
            ),
            content_info=ContentInfo(
                domain="IT services",
                key_terms=["earnings", "실적", "call", "발표"],
                action_type="earnings call",
                confidence=0.95
            ),
            original_query="What are the details of Samsung SDS's Q4 2024 earnings call scheduled for January 23, 2025?"
        ),
        QueryAnalysis(
            thought_process=[
                "First, I identify the main entities: Found KRAFTON, Inc. as the primary company",
                "Then, I determine company origins: KRAFTON is a South Korean company (formerly Bluehole)",
                "Next, I analyze temporal references: From email metadata, we have Jan 24, 2025 date",
                "Then, I identify domain and content-specific terms: Gaming industry, specifically focusing on new game releases",
                "Finally, I assess confidence: High confidence due to email metadata and clear subject"
            ],
            company_info=CompanyInfo(
                name="KRAFTON, Inc.",
                origin="South Korea",
                variations=["크래프톤", "KRAFTON", "Bluehole", "블루홀", "PUBG Corporation", "PUBG Corp", "259960.KR"],
                confidence=0.95
            ),
            temporal_info=TemporalInfo(
                years=None,
                months=None,
                quarter=QuarterInfo(number=None, year=None),
                confidence=0
            ),
            content_info=ContentInfo(
                domain="gaming",
                key_terms=["new game", "game release", "game"],
                action_type="announcement",
                confidence=0.95
            ),
            original_query="Summarize KRAFTON, Inc.'s recent announcements regarding new game releases."
        ),
        QueryAnalysis(
            thought_process=[
                "First, I identify the main entities: Found Zeta Global as the primary company",
                "Then, I determine company origins: Zeta Global is a US company",
                "Next, I analyze temporal references: August 2024 with prior months due to 'recent'",
                "Then, I identify domain and content-specific terms: Focus on SEC filing announcements",
                "Finally, I assess confidence: High confidence on company, slightly lower on temporal range"
            ],
            company_info=CompanyInfo(
                name="Zeta Global",
                origin="United States", 
                variations=["Zeta", "ZETA", "Zeta Global"],
                confidence=0.9
            ),
            temporal_info=TemporalInfo(
                years=[2024],
                months=[3, 4, 5, 6, 7, 8],
                quarter=QuarterInfo(number=3, year=2024),
                confidence=0.8
            ),
            content_info=ContentInfo(
                domain="regulatory",
                key_terms=["SEC", "filing"],
                action_type="regulatory filing",
                confidence=0.9
            ),
            original_query="What recent SEC filing did Zeta Global announce as of August 2024"
        ),
        QueryAnalysis(
            thought_process=[
                "First, I identify the main entities: Found Atara Biotherapeutics and their product Tabelecleucel",
                "Then, I determine company origins: US biotech company",
                "Next, I analyze temporal references: No specific time mentioned in query",
                "Then, I identify domain and content-specific terms: Focus on biotherapeutic/drug development",
                "Finally, I assess confidence: High on company and domain, no temporal markers"
            ],
            company_info=CompanyInfo(
                name="Atara Biotherapeutics",
                origin="United States",
                variations=["Atara", "ATRA", "Atara Bio"],
                confidence=0.9
            ),
            temporal_info=TemporalInfo(
                years=None,
                months=None,
                quarter=QuarterInfo(number=None, year=None),
                confidence=0
            ),
            content_info=ContentInfo(
                domain="biotechnology",
                key_terms=["tabelecleucel", "report", "drug"],
                action_type="announcement",
                confidence=0.9
            ),
            original_query="What did Atara Biotherapeutics announce regarding Tabelecleucel"
        ),
        QueryAnalysis(
            thought_process=[
                "First, I identify the main entities: Found Starbucks as primary company",
                "Then, I determine company origins: US coffee chain company",
                "Next, I analyze temporal references: Recovery FROM 2024Q2 implies looking at immediate post-Q2 period",
                "Then, I identify domain and content-specific terms: Focus on multiple recovery strategies from business struggles",
                "Finally, I assess confidence: High on company info, temporal frame more focused on immediate recovery period"
            ],
            company_info=CompanyInfo(
                name="Starbucks",
                origin="United States", 
                variations=["Starbucks", "SBUX", "Starbucks Coffee"],
                confidence=0.95
            ),
            temporal_info=TemporalInfo(
                years=[2024],
                months=[3, 4, 5, 6, 7, 8, 9],
                quarter=QuarterInfo(number=2, year=2024),
                confidence=0.8
            ),
            content_info=ContentInfo(
                domain="retail/food service",
                key_terms=["strategy", "recovery", "business"],
                action_type="recovery strategy",
                confidence=0.9
            ),
            original_query="Summarize Starbucks' strategies to recover from its 2024Q2 struggles"
        )
    ]
    return examples

def load_test_queries() -> List[Dict]:
    """Load test queries from the qa_pairs.json file."""
    with open(QA_PAIRS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def display_filter(filter_dict: dict):
    """Display filter conditions in a formatted table"""
    table = Table(title="Filter Conditions")
    table.add_column("Component", style="cyan")
    table.add_column("Conditions", style="green")
    
    if not filter_dict:
        table.add_row("Filter", "Empty (low confidence)")
        console.print(table)
        return
    
    # Company filter
    if "$and" in filter_dict:
        conditions = filter_dict["$and"]
        
        for condition in conditions:
            if "$or" in condition:
                # Company or Content conditions
                field_conditions = condition["$or"]
                sample_field = list(field_conditions[0].keys())[0]
                
                if "company" in sample_field:
                    component = "Company Filter"
                    details = "\n".join(
                        f"{list(c.keys())[0]}: {list(c.values())[0]['$in']}" 
                        for c in field_conditions
                    )
                elif "key_terms" in sample_field:
                    component = "Content Terms Filter"
                    details = "\n".join(
                        f"{list(c.keys())[0]}: {list(c.values())[0]['$in']}" 
                        for c in field_conditions
                    )
                else:
                    component = "Other Filter"
                    details = str(field_conditions)
                
                table.add_row(component, details)
            
            elif "$and" in condition:
                # Temporal or Content conditions
                sub_conditions = condition["$and"]
                details = []
                
                for c in sub_conditions:
                    field = list(c.keys())[0]
                    value = list(c.values())[0]
                    
                    if "$in" in value:
                        details.append(f"{field}: {value['$in']}")
                    elif "$eq" in value:
                        details.append(f"{field}: {value['$eq']}")
                    elif "$or" in c:
                        # Handle key terms
                        term_conditions = c["$or"]
                        terms = []
                        for tc in term_conditions:
                            field = list(tc.keys())[0]
                            value = list(tc.values())[0]["$in"][0]
                            terms.append(value)
                        details.append(f"key_terms: {terms}")
                
                if any("year" in d or "month" in d for d in details):
                    table.add_row("Temporal Filter", "\n".join(details))
                else:
                    table.add_row("Content Filter", "\n".join(details))
            
            elif "metadata.domain" in condition:
                table.add_row("Domain Filter", f"{condition['metadata.domain']['$eq']}")
            
            elif "metadata.action_type" in condition:
                table.add_row("Action Type Filter", f"{condition['metadata.action_type']['$eq']}")
    
    console.print(table)

@app.command()
def test_manual(example_idx: int = typer.Argument(..., help="Index of manual example to test")):
    """Test filter builder with manual examples"""
    examples = get_manual_examples()
    if not 0 <= example_idx < len(examples):
        console.print(f"[red]Error: Invalid example index. Must be between 0 and {len(examples)-1}[/red]")
        return
    
    example = examples[example_idx]
    builder = ElasticsearchFilterBuilder(company_variation_limit=4, content_term_limit=4)
    
    # Display original query and analysis
    console.rule("[bold]Original Query")
    console.print(example.original_query)
    console.print()
    
    console.rule("[bold]Thought Process")
    for step in example.thought_process:
        console.print(f"• {step}")
    console.print()
    
    # Build and show individual filter components
    must_conditions = []
    
    # Company filter
    if example.company_info.confidence > 0.5 and example.company_info.variations:
        company_filter = builder._build_company_filter(example.company_info.variations)
        if company_filter:
            must_conditions.append(company_filter)
            console.rule("[bold]Company Filter")
            console.print(json.dumps(company_filter, indent=4))
    
    # Temporal filter
    if example.temporal_info.confidence > 0.5:
        temporal_filter = builder._build_temporal_filter(example.temporal_info)
        if temporal_filter:
            must_conditions.extend(temporal_filter)
            console.rule("[bold]Temporal Filter")
            console.print(json.dumps(temporal_filter, indent=4))
    
    # Content filter
    if example.content_info.confidence > 0.5:
        content_filter = builder._build_content_filter(example.content_info)
        if content_filter:
            must_conditions.append(content_filter)
            console.rule("[bold]Content Filter")
            console.print(json.dumps(content_filter, indent=4))
    
    # Get and show the final Elasticsearch query
    es_query = builder.build_filter(example)
    console.rule("[bold]Final Elasticsearch Query")
    console.print(json.dumps(es_query, indent=2))

@app.command()
def test_qa(idx: int = typer.Argument(..., help="Index in qa_pairs.json to test")):
    """Test filter builder with QA test cases"""
    # Load test case
    queries = load_test_queries()
    if not 0 <= idx < len(queries):
        console.print(f"[red]Error: Invalid test case index. Must be between 0 and {len(queries)-1}[/red]")
        return
    
    test_case = queries[idx]
    query = test_case['Question']
    
    # Initialize components
    analyzer = QueryAnalyzer()
    filter_builder = ElasticsearchFilterBuilder()
    
    # Run pipeline
    console.rule("[bold]Test Case Information")
    console.print(f"[bold]Index:[/] {idx}")
    console.print(f"[bold]Query:[/] {query}")
    console.print()
    
    # Get analysis
    console.rule("[bold]Query Analysis")
    analysis = analyzer.invoke(query)
    
    # Display thought process
    for step in analysis.thought_process:
        console.print(f"• {step}")
    console.print()
    
    # Build and display filter
    filter_dict = filter_builder.build_filter(analysis)
    console.rule("[bold]Generated Filter")
    display_filter(filter_dict)

@app.command()
def test_all():
    """Run all test cases"""
    # Test manual examples
    console.rule("[bold]Testing Manual Examples")
    examples = get_manual_examples()
    for i in range(len(examples)):
        console.rule(f"[bold]Manual Example {i}")
        test_manual(i)
        console.print()
    
    # Test QA examples
    console.rule("[bold]Testing QA Examples")
    queries = load_test_queries()
    for i in range(min(5, len(queries))):
        console.rule(f"[bold]QA Example {i}")
        test_qa(i)
        console.print()

    # Build and display filter
    filter_dict = filter_builder.build_filter(analysis)
    console.rule("[bold]Generated Filter")
    display_filter(filter_dict)

@app.command()
def test_all():
    """Run all test cases"""
    # Test manual examples
    console.rule("[bold]Testing Manual Examples")
    examples = get_manual_examples()
    for i in range(len(examples)):
        console.rule(f"[bold]Manual Example {i}")
        test_manual(i)
        console.print()
    
    # Test QA examples
    console.rule("[bold]Testing QA Examples")
    queries = load_test_queries()
    for i in range(min(5, len(queries))):
        console.rule(f"[bold]QA Example {i}")
        test_qa(i)
        console.print()

if __name__ == "__main__":
    app()