from typing import Dict, List, Any, Optional
import json
from datetime import datetime

from pipeline.common.base_agent import BaseAgent
from pipeline.common.prompt import QUERY_ANALYZER_PROMPT_TEMPLATE
from pipeline.common.example_messages import get_query_analyzer_messages
from pipeline.retrieval.schema import QueryAnalysis, CompanyInfo, TemporalInfo, QuarterInfo

class QueryAnalyzer(BaseAgent):
    def get_example_messages(self) -> List[Dict[str, str]]:
        return get_query_analyzer_messages()

    def get_prompt(self, input_data: Any) -> str:
        current_date = datetime.now()
        return QUERY_ANALYZER_PROMPT_TEMPLATE.format(
            query=input_data["query"],
            year=current_date.year,
            month=current_date.month
        )

    def validate_output(self, output: str) -> Optional[Dict]:
        try:
            analysis_dict = json.loads(output)
            
            # Add original query if not present
            if "original_query" not in analysis_dict:
                analysis_dict["original_query"] = analysis_dict.get("query", "")
                
            # Handle company_info if it's a list
            if isinstance(analysis_dict.get("company_info"), list) and len(analysis_dict["company_info"]) > 0:
                company = analysis_dict["company_info"][0]
                analysis_dict["company_info"] = CompanyInfo(
                    name=company.get("name"),
                    origin=company.get("origin", None),
                    variations=company.get("variations", []),
                    confidence=company.get("confidence", 0.0)
                ).model_dump()
            
            # Handle quarter info validation
            temporal_info = analysis_dict["temporal_info"]
            quarter_data = temporal_info.get("quarter")
            
            # If quarter data exists, validate it
            if quarter_data:
                # If both fields are null, set quarter to None
                if quarter_data.get("number") is None and quarter_data.get("year") is None:
                    temporal_info["quarter"] = None
                else:
                    # Otherwise try to create QuarterInfo
                    try:
                        temporal_info["quarter"] = QuarterInfo(**quarter_data)
                    except ValueError:
                        # If validation fails, set quarter to None
                        temporal_info["quarter"] = None
            
            # Validate with Pydantic model
            validated = QueryAnalysis(**analysis_dict)
            return validated.dict()
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLM response as JSON: {e}")
            return None
        except Exception as e:
            print(f"Failed to create QueryAnalysis object: {e}")
            return None

    def invoke(self, query: str) -> Optional[QueryAnalysis]:
        """Main entry point for query analysis.
        
        Args:
            query: The query string to analyze
            
        Returns:
            QueryAnalysis object if successful, None if parsing fails
        """
        if not query or not isinstance(query, str):
            print("Query must be a non-empty string")
            return None
            
        output = super().invoke({"query": query})
        if not output:
            return None
            
        try:
            return QueryAnalysis(**output)
        except Exception as e:
            print(f"Failed to create QueryAnalysis from output: {e}")
            return None
