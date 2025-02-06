from typing import Dict, List, Any
from pipeline.retrieval.schema import QueryAnalysis

class ElasticsearchFilterBuilder:
    def __init__(self, company_variation_limit: int = 10, content_term_limit: int = 10):
        """Initialize the filter builder with configurable limits
        
        Args:
            company_variation_limit: Maximum number of company name variations per field (default: 1000 to effectively use all variations)
            content_term_limit: Maximum number of content terms in subject search (default: 1000 to effectively use all terms)
        """
        self.company_variation_limit = company_variation_limit
        self.content_term_limit = content_term_limit

    def build_filter(self, analysis: QueryAnalysis) -> Dict:
        if not analysis:
            return {}
            
        must_conditions = []
        
        # Build company filter if confidence is high enough
        if hasattr(analysis, 'company_info') and analysis.company_info:
            if analysis.company_info.confidence > 0.5 and analysis.company_info.variations:
                company_filters = self._build_company_filter(
                    analysis.company_info.variations
                )
                if isinstance(company_filters, list):
                    must_conditions.extend(company_filters)
                elif company_filters:
                    must_conditions.append(company_filters)
        
        # Build temporal filter
        if hasattr(analysis, 'temporal_info') and analysis.temporal_info:
            if analysis.temporal_info.confidence > 0.5:
                temporal_filter = self._build_temporal_filter(
                    analysis.temporal_info
                )
                if temporal_filter:
                    must_conditions.extend(temporal_filter)
        
        # Build content filter
        if hasattr(analysis, 'content_info') and analysis.content_info:
            if analysis.content_info.confidence > 0.5:
                content_filter = self._build_content_filter(
                    analysis.content_info
                )
                if content_filter:
                    must_conditions.append(content_filter)
        
        # Convert must conditions to should conditions with boosts
        should_conditions = []
        
        # Company match is most important
        if len(must_conditions) > 0 and "bool" in must_conditions[0]:
            company_cond = {"bool": {**must_conditions[0]["bool"], "boost": 1.5, "_name": "company_match"}}
            should_conditions.append(company_cond)
        
        # Temporal match is next most important
        # Look for the temporal filter we built
        temporal_filter = next((c for c in must_conditions if isinstance(c, dict) and 
                              c.get("bool", {}).get("_name") == "temporal_match"), None)
        if temporal_filter:
            should_conditions.append(temporal_filter)
        
        # Content match terms - content filter is always added last
        if must_conditions and must_conditions[-1].get("bool", {}).get("should") and analysis.content_info:
            # Get the last condition which should be the content filter
            content_filter = must_conditions[-1]
            # Remove any company-related conditions that might have been caught
            content_terms = []
            if analysis.content_info.key_terms:
                content_terms.extend(analysis.content_info.key_terms)
            if analysis.content_info.action_type:
                content_terms.append(analysis.content_info.action_type)
            
            content_should = [c for c in content_filter["bool"]["should"] 
                            if any(term in c["wildcard"][list(c["wildcard"].keys())[0]]["value"] 
                                  for term in content_terms)]
            if content_should:
                cond = {"bool": {"should": content_should, "minimum_should_match": 1, "boost": 1.5, "_name": "content_match"}}
                should_conditions.append(cond)
        
        # Return query that combines vector search with metadata matching
        if not should_conditions:
            return {}
            
        return {
            "bool": {
                "should": should_conditions,
                "minimum_should_match": 1  # Require at least one match
            }
        }

    def _build_company_filter(self, variations: List[str]) -> Dict:
        """Build company filter for Elasticsearch, limiting variations per field"""
        if not variations:
            return {}
        
        # Take only first N variations for efficiency
        variations = variations[:self.company_variation_limit]
        must_conditions = []
        
        # Build single should block across all fields
        all_fields = ["metadata.sender_name", "metadata.sender_email", "metadata.subject", "text"]
        field_conditions = []
        
        # Add wildcards for each field and variation combination
        for field in all_fields:
            for variation in variations:
                field_conditions.append({
                    "wildcard": {
                        field: {
                            "value": f"*{variation}*",
                            "case_insensitive": True
                        }
                    }
                })
        
        # Single should block - any match gives the boost
        if field_conditions:
            must_conditions.append({
                "bool": {
                    "should": field_conditions,
                    "minimum_should_match": 1
                }
            })
        
        return must_conditions[0] if len(must_conditions) == 1 else {
            "bool": {
                "must": must_conditions
            }
        }

    def _build_temporal_filter(self, temporal_info) -> List[Dict]:
        """Build temporal filter for Elasticsearch"""
        conditions = []
        
        # Initialize temporal conditions
        temporal_conditions = []
        
        # Year and month conditions
        if hasattr(temporal_info, 'years') and temporal_info.years:
            if isinstance(temporal_info.years, list):
                temporal_conditions.append({"terms": {"metadata.year": temporal_info.years}})
            else:
                temporal_conditions.append({"term": {"metadata.year": temporal_info.years}})
        
        if hasattr(temporal_info, 'months') and temporal_info.months:
            temporal_conditions.append({"terms": {"metadata.month": temporal_info.months}})
        
        # Quarter condition - search for Q1, Q2, etc. in text and subject
        if hasattr(temporal_info, 'quarter') and temporal_info.quarter:
            quarter = temporal_info.quarter
            if quarter.number is not None and quarter.year is not None and len(quarter.number) == len(quarter.year):
                quarter_conditions = []
                
                # For each quarter-year combination
                for q, y in zip(quarter.number, quarter.year):
                    # Add wildcard searches for various quarter formats
                    # Get last 2 digits of year for YY format
                    yy = str(y)[-2:]
                    quarter_terms = [
                        f"*Q{q}*{yy}*",     # Q2 24
                        f"*{yy}*Q{q}*",     # 24 Q2
                        f"*{q}Q*{yy}*",     # 2Q 24
                        f"*{yy}*{q}Q*",     # 24 2Q
                        f"*{yy}*{q}분기*"    # 24 2분기
                    ]
                    
                    for term in quarter_terms:
                        # Search in both subject and text
                        for field in ["metadata.subject", "text"]:
                            quarter_conditions.append({
                                "wildcard": {
                                    field: {
                                        "value": term,
                                        "case_insensitive": True
                                    }
                                }
                            })
                
                if quarter_conditions:
                    temporal_conditions.append({
                        "bool": {
                            "should": quarter_conditions,
                            "minimum_should_match": 1
                        }
                    })
        
        # Add all temporal conditions with a single boost
        if temporal_conditions:
            temporal_filter = {
                "bool": {
                    "should": temporal_conditions,
                    "minimum_should_match": 1,
                    "boost": 1.5,
                    "_name": "temporal_match"
                }
            }
            conditions.append(temporal_filter)
        
        return conditions
    
    def _build_content_filter(self, content_info) -> Dict:
        """Build content filter for Elasticsearch, limiting subject values total"""
        should_conditions = []
        
        # Collect all possible terms
        terms = []
        if content_info.key_terms:
            terms.extend(content_info.key_terms)
        if content_info.action_type:
            terms.append(content_info.action_type)
            
        # Take only first N terms total
        for term in terms[:self.content_term_limit]:
            # Search in both subject and text fields
            for field in ["metadata.subject", "text"]:
                should_conditions.append({
                    "wildcard": {
                        field: {
                            "value": f"*{term}*",
                            "case_insensitive": True
                        }
                    }
                })
        
        return {
            "bool": {
                "should": should_conditions,
                "minimum_should_match": 1
            }
        } if should_conditions else {}
