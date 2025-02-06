from typing import List, Dict

EMAIL_CLASSIFICATION_PROMPT_TEMPLATE = """Please classify this email for inclusion in our financial investment research RAG system based on the following information:

METADATA:
Topic: {topic}
Subject: {subject}
From: {sender_name} ({sender_email})
To: {to}
Conversation Topic: {conversation_topic}

CONTENT:
{body}

ATTACHMENTS:
{attachment_content}

CLASSIFICATION TASK:
Analyze if this email should be included in an investment research database used by professional investors for market research, company analysis, and investment decisions.

Your response must be in this exact JSON format:
{{
    "thought_process": [
        "First, I analyze the sender and context: [who sent it and why]",
        "Then, I examine the core content and attachments: [key information/topics covered in both email and attachments]",
        "Next, I identify any investment relevance: [specific financial/market/investment value]",
        "Finally, I match it to classification criteria: [which category it fits and why]"
    ],
    "decision": "INCLUDE/EXCLUDE",
    "category": "[category from below]",
}}

EXCLUSION CATEGORIES (If any of these fit, exclude):
1. Non-Financial Onboarding/Welcome Emails
   → Generic welcome messages, app introductions (e.g., "Welcome to LinkedIn")
2. Email Delivery Failures
   → Bounce backs, undeliverable notices
3. Non-Financial Service Emails
   → Regular billing/receipts, subscription notifications
4. Schedule/Reminder Emails
   → Basic meeting reminders without content, calendar invites
5. Social Media Notifications
   → Platform notifications, unless specifically about financial news
6. Security/Account Notifications
   → Password resets, login alerts, security checks
7. General HR/Internal Emails
   → Office policies, holidays, internal updates

INCLUSION CATEGORIES (Must provide investment value):
1. Finance-Focused Product/Service Information
   → Financial research platforms, investment tools (e.g., Bloomberg, AlphaSense)
2. Earnings/Financial Data/Corporate Actions
   → Earnings releases, 10-K/Q filings, M&A news, dividends
3. Investment Events
   → Earnings calls, investor conferences, company presentations
4. Finance/Business Related Discussions
   → Investment analysis, market research, strategy discussions
5. Alternative Data Insights
   → Market trends, sentiment analysis, alternative metrics
6. Legal/Regulatory Updates
   → Investment-related regulation changes, policy impacts

KEY GUIDELINES:
- Focus on investment research value, not administrative value
- When in doubt about investment relevance, EXCLUDE
- Include if contains unique financial insights or data
- Context matters: even routine emails may be included if they contain valuable investment information"""


EMAIL_QA_PROMPT_TEMPLATE = '''Generate one high-quality investment research question-answer pair from this email content. The Q&A should help investors find and analyze relevant information from a large email database.

EMAIL METADATA:
Subject: {subject}
From: {sender_name} ({sender_email})
To: {to}
Received Time: {received_time}
Conversation Topic: {conversation_topic}

CONTENT:
{body}

ATTACHMENTS:
{attachment_content}

Your response must be in this JSON format:
{{
    "thought_process": [
        "First, I identify the key information type: [company announcement/market data/analyst view/strategic update/corporate action]",
        "Then, I randomly select a question format from the list to ensure variation: [Simple Factual/Synthesis/Timeline/Cross-Reference/Numerical/Impact/Source-Specific/Comparative].",
        "Next, I ensure the question is investment-research friendly: [Natural time frame/Clear entities/Retrievable/Multi-language compatible]",
        "Finally, I craft a concise, fact-based answer: [Key numbers/Core facts/Relevant metrics]"
    ],
    "question": "[Randomly selected question type applied to the email content]",
    "answer": "[1-2 sentence factual answer with key metrics when available]"
}}

RULES FOR VARIATION:
1. Randomly select** a question type each time to avoid repetition.
2. Do not use 'Numerical' unless all other types have already been used.** Prioritize other formats first.
3. Rotate through different question types in a natural manner** while ensuring diverse investment insights.

QUESTION BEST PRACTICES:
1. Use natural time frames ("in 2024", "during Q3", "early 2025").
2. Make questions work across languages (many source emails are in Korean/Japanese).
3. Focus on investment-relevant information.
4. Enable connection of related information.
5. Support both quick lookups and deeper analysis.
6. Avoid overly specific dates (like exact day).
7. Ensure retrievability from email content.

ANSWER BEST PRACTICES:
1. Keep to 1-2 sentences.
2. Include key numbers/metrics when available.
3. Focus on facts, not speculation.
4. Start with core information.
5. Use clear financial terminology.
6. Match the question's scope.

RANDOM QUESTION TYPES (Prioritize Non-Numerical First, Only Use Numerical Last)**
1. **Simple Factual** ("What did [Company] announce about [Topic] in [Period]?")
2. **Synthesis** ("Summarize [Company]'s [Actions] in [Period]")
3. **Timeline** ("How did [Topic/Metric] develop during [Period]?")
4. **Cross-Reference** ("How did [Event A] relate to [Event B]?")
5. **Impact** ("What effects did [Event] have on [Metric/Market]?")
6. **Source-Specific** ("What did [Source] report about [Topic]?")
7. **Comparative** ("How does [Company A]'s [Metric] compare to [Company B]?")
8. **Numerical** ("What were the key figures from [Event] in [Period]?" - **Only if other question types aren't appropriate**)

Remember: Questions should be natural for investment research workflows and support effective retrieval from a large email database.'''


QUERY_ANALYZER_PROMPT_TEMPLATE = """Analyze this query for company, temporal, and content information.
Current Reference Date: {year}-{month}
Query: {query}

For companies:
1. Identify company names and core information:
   - Primary company name
   - Country of origin
   - Industry context and market position

2. Generate name variations with strict ordering priority:
   - Primary/shortest clear English name (must be meaningful)
   - Stock ticker ONLY if major listed company (e.g., SBUX, ATRA)
   - Common alternative English forms
   - For non-English companies:
     * Primary native script (after English)
     * Full native script variations

   Examples of good ordering:
   - Samsung SDS -> ["Samsung", "삼성", "Samsung SDS", "삼성SDS"]
   - Starbucks -> ["Starbucks", "SBUX", "Starbucks Coffee"]
   - Atara -> ["Atara", "ATRA", "Atara Bio"]
   - Shin-Etsu -> ["Shin-Etsu", "信越", "Shinetsu", "信越化学工業"]

   Avoid:
   - Single letters/ambiguous terms (e.g., "K" alone)
   - Redundant legal forms (e.g., "Co., Ltd.", "Inc.")
   - Overly formal variations
   - Partial/incomplete names

3. Special case - Non-English Company Ordering:
   For companies from non-English speaking countries:
   1. English form MUST always come first
   2. Native script form follows
   3. Full/longer forms follow same pattern

   Examples:
   - Korean: 
     * ["Samsung", "삼성", "Samsung SDS", "삼성SDS"]
     * ["Krafton", "크래프톤", "Krafton Gaming", "크래프톤 게이밍"]
   - Japanese:
     * ["Shin-Etsu", "信越", "Shinetsu", "信越化学工業"]

For temporal information:
For temporal information:
1. Basic handling:
   - Convert all months to integers (1-12)
   - Include complete quarter periods plus specific dates
   - If no temporal info: all null, confidence = 0
   - When ONLY relative terms present (no explicit dates):
     * Calculate from current date: {year}-{month}
     * "Recent": last 3-6 months 
     * "Latest": last 3 months
     * Example: If reference date 2025-2, and query only has "recent":
       - months=[9,10,11,12,1,2]
       - years=[2024,2025]

   Note: Use explicit dates if present in query. Only use reference date
   when query has ONLY relative time terms like "recent" or "latest"
   without any specific dates mentioned.

2. Quarter period guidelines:
   - Q1: months=[3,4,5,6,7,8]
   - Q2: months=[3,4,5,6,7,8,9]
   - Q3: months=[6,7,8,9,10,11,12]
   - Q4: months=[10,11,12,1,2,3]
     * ALWAYS include quarter info when specific quarter mentioned
     * Example: "Q2 2024" -> quarter: {{"number": [2], "year": [2024]}}

3. Special cases:
   - Earnings/reports: quarter months + announcement date
   - "Recent": 3-6 months prior from current date ({year}-{month})
   - "Latest": most recent 3 months from current date ({year}-{month})
   - "Recovery/response": period after referenced time
   - Multi-year: include all relevant years (e.g., Q4 2024 + Jan 2025)

For content information:
1. Key terms with strict priority order:
   - Core business terms (e.g., "earnings", "drug")
   - Native translations for non-English companies
   - Specific product/technical terms
   - Keep compound terms only if adding unique value

   Examples of good ordering:
   - Earnings: ["earnings", "실적", "call", "발표"]
   - Product: ["tabelecleucel", "report", "drug"]
   - Strategy: ["strategy", "recovery", "business"]

2. Key term guidelines:
   - Focus on business/domain-specific terms
   - Skip generic words ("details", "about", "scheduled")
   - Avoid redundant compounds if individual words exist
   - No time-related terms as key terms
   - Use singular forms unless plural has distinct meaning

3. Special case - Non-English Company Terms:
   For non-English companies, key terms MUST follow:
   1. Each English term IMMEDIATELY followed by its native translation
   2. Then move to next term-translation pair

   Examples:
   - Korean company:
     * ["earnings", "실적", "call", "발표"]  // each English term with its Korean translation
     * ["game", "게임", "release", "출시"]   // immediate pairing pattern
   - Japanese company:
     * ["earnings", "決算", "report", "報告"]
     * ["share", "株式", "buyback", "買戻"]
   - Chinese company:
     * ["revenue", "营收", "growth", "增长"]
     * ["sales", "销售", "target", "目标"]
     
Confidence Scoring:
- High (0.9-0.95): Well-known companies, explicit dates, clear actions
- Medium (0.8-0.89): Less specific ranges, derived information
- Low (0.7-0.79): Vague references, uncommon companies
- Zero: Missing or uncertain information

Output JSON with:
{{
    "thought_process": [clear steps explaining reasoning],
    "company_info": {{
        "name": "primary name",
        "origin": "country",
        "variations": ["ordered by search priority"],
        "confidence": 0-1
    }},
    "temporal_info": {{
        "years": [list of integers] or null,
        "months": [list of integers 1-12] or null,
        "quarter": {{
            "number": 1-4 or null,
            "year": integer or null
        }},
        "confidence": 0-1
    }},
    "content_info": {{
        "domain": "business domain",
        "key_terms": ["ordered by search effectiveness"],
        "action_type": "specific action",
        "confidence": 0-1
    }},
    "original_query": "query string"
}}"""

GENERATOR_PROMPT_TEMPLATE = """You are the final component in a retrieval-augmented generation (RAG) system dedicated to answering questions about email threads and attached content. The pipeline so far has:
1. Received a user query
2. Retrieved the most relevant email conversations (each containing multiple chunks representing email bodies, PDFs, or other attachments)
3. Passed you the context (these chunks) and the original query

YOUR TASK:
1. Analyze Query Context
   - Parse the query: "{query}"
   - If query involves time references ("recent", "latest", "past year") without explicit dates, use reference date: {year}-{month}
   - Identify query type: timeline/historical, financial/performance, general analysis
   - Determine required information types and depth

2. Process Retrieved Context
   - Review all conversations and chunks
   - Map relevant chunks to information needs
   - Note gaps or limitations in available data
   - Discard irrelevant content with clear reasoning
   
   DOCUMENT ANALYSIS GUIDELINES:
   - Identify document types within conversations:
      • Email bodies: Direct communications, summaries
      • PDF attachments: Reports, presentations, official documents
      • DOCX attachments: Detailed analysis, transcripts
      • XLSX attachments: Spreadsheets of specific numerical data

   - Look for patterns across chunks:
      • Q&A formats with timestamps suggest interviews
      • Regular date patterns suggest periodic reports
      • Numbered sections indicate structured documents
      • Cross-references between chunks indicate related content

3. Plan Response Structure
   Based on query type, follow these templates:

   TIMELINE/HISTORICAL:
   • Chronological organization with period markers
   • Category-based sections (Product, Financial, Regulatory, etc.)
   • Impact indicators for major events
   • Multiple detail levels (main event -> implications)

   FINANCIAL/PERFORMANCE:
   • Executive summary highlighting key trends
   • Period-by-period breakdown with consistent metrics
   • Segment analysis with growth drivers
   • Year-to-date or comparative analysis when relevant

   GENERAL ANALYSIS:
   • Topic-based organization
   • Clear information hierarchy
   • Supporting evidence and context
   • Impact assessment and implications

4. Format Requirements
   - All newline characters inside JSON responses must be properly escaped as "\\n" instead of raw newlines.
   - Use "\n\n" for major section breaks
   - Use "\n" for line breaks within sections
   - Use "•" for main bullets, "-" for sub-bullets
   - Consistent indentation for hierarchical information
   - Clear category headers
   - Standard metric presentation:
     Example: "Revenue: $XX (+Y% QoQ, +Z% YoY)"

5. Source Attribution
   - Specify document types (interview, report, analysis)
   - Include timing (document date)
   - Provide context (e.g. when a prompt asked for internal sources: "Based on internal expert interview...")
   - Indicate authority level (expert analysis, official report)

5. Return Response in This Exact JSON Format:
FINAL RESPONSE FORMAT:
{{
    "thought_process": [
        "First, I analyze the query '[QUERY]' and identify it as [query type]. Given reference date {year}-{month}, this covers [time period].",
        
        "Then, I examine retrieved documents for relevant data:",
        "- Conversation X (chunk_id) contains [document type] showing [specific content]",
        "- Conversation Y (chunk_id) includes [document type] with [specific content]",
        "Other conversations excluded because [reason]",
        
        "Next, I structure the response following [template type] format:",
        "- Main sections: [list sections]",
        "- Key metrics/events to highlight",
        "- Organization method",
        
        "Finally, I ensure comprehensive coverage and clear progression of information"
    ],
    "response": "[Well-structured answer following template format with proper source attribution and escape characters]",
    "answer": {{
        "chunk_id": "Specific contribution of this chunk to the response and document type",
        "chunk_id": "Specific contribution of this chunk to the response and document type"
    }}
}}

REQUIREMENTS:
- Chunk IDs must be numeric
- Response must follow template structure for query type
- All metrics/dates must be properly contextualized
- Include business impact and implications where relevant
- Maintain consistent formatting throughout
- Ensure logical flow and clear progression
- Provide comprehensive coverage while staying focused
- Properly attribute information to specific document types and sources

Current Reference Date: {year}-{month}

QUESTION:
{query}

RETRIEVED EMAIL CONVERSATIONS:
{context}"""