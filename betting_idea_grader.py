from datetime import datetime
import os
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langchain_community.tools.tavily_search import TavilySearchResults
from betting_pool_generator import BettingPoolGeneratorOutput
from common import smol_llm
from common import big_llm


class EvidenceSearchQueries(BaseModel):
    evidence_search_queries: list[str]


class BettingPoolIdeaGraderOutput(BaseModel):
    result: str  # Required
    probabilities: Optional[dict[str, float]] = None
    sources: list[str]
    explanation: str
    time_period_analysis: Optional[dict] = Field(default_factory=dict)


class Evidence(BaseModel):
    url: str
    summary: str
    search_query: str
    # supports: WinLoseConditions


class BettingPoolIdeaGraderGraphOutput(MessagesState):
    betting_pool_idea: BettingPoolGeneratorOutput
    evidence_search_queries: list[str]
    evidence: list[Evidence]
    betting_pool_idea_result: BettingPoolIdeaGraderOutput


tavily_search = TavilySearchResults(
    max_results=2,
    include_answer=True,
    include_raw_content=True,
    include_images=False,
    # search_depth="advanced", # Unclear what this does
)


def betting_pool_grading_preamble(betting_pool: dict):
    return f"""
 You are a betting pool idea grader with expertise in data analysis and probability assessment.
    
    This is what users are betting on in this pool: 
    - {betting_pool['betting_pool_idea']}
  
    This betting pool has two mutually exclusive outcomes, "yes/positive" and "no/negative". There will never be a tie or a grey area between the two options.
    
    Below are the conditions in which either option will win or lose:
    - Condition in which "yes" will win: {betting_pool['options']['yes']['win_condition']}
    - Condition in which "yes" will lose: {betting_pool['options']['yes']['lose_condition']}
    - Condition in which "no" will win: {betting_pool['options']['no']['win_condition']}
    - Condition in which "no" will lose: {betting_pool['options']['no']['lose_condition']}"""


def generate_evidence_queries(state: BettingPoolIdeaGraderGraphOutput):
    """Grade the betting pool idea"""
    print(f"state in generate_evidence_queries: {state}")
    print("Grading betting pool idea")

    betting_pool = state.get("betting_pool_idea")
    print(f"betting_pool in generate_evidence_queries: {betting_pool}")

    evidence_search_sys_msg = SystemMessage(
        content=f"""
    Your task is to generate 3 search queries for finding evidence about the outcome of a betting pool.
    
    IMPORTANT TIME CONTEXT:
    - Focus on the actual time period mentioned in the question (e.g., "Q1 2024", "January 2024", etc.)
    - If the question refers to a specific time period that has already passed, prioritize finding final/official results
    - For questions about specific quarters/periods, ensure to include the company's official reporting dates
    
    Generate queries that will:
    1. Find official results/data for the specified time period
    2. Find company announcements or official statements
    3. Find reliable third-party verification of the results
    
    Your queries should focus on finding CONCLUSIVE evidence, even if the pool's decision date hasn't arrived yet.
    
    response must be a JSON object with the following fields, and nothing else:
    {{
        "evidence_search_queries": ["query1", "query2", "query3"], // List of 3 search queries
    }}
    """
    )

    evidence_search_user_msg = HumanMessage(
        content=f"""
    Here is the betting pool information:

    BETTING POOL IDEA:
    {betting_pool.get("betting_pool_idea")}

    OPTIONS:
    {betting_pool.get("options")}

    CLOSURE SUMMARY:
    {betting_pool.get("closure_summary")}

    CLOSURE INSTRUCTIONS:
    {betting_pool.get("closure_instructions")}

    Please generate search queries that will help find evidence to verify these conditions.
    """
    )

    structured_llm = big_llm.with_structured_output(EvidenceSearchQueries)
    result = structured_llm.invoke([evidence_search_sys_msg, evidence_search_user_msg])
    print("Evidence search result:", result)
    return {
        "evidence_search_queries": result.evidence_search_queries,
    }


def gather_evidence(state: BettingPoolIdeaGraderGraphOutput):
    """Gather evidence from search queries"""
    print("Gathering evidence from search queries")

    betting_pool = state.get("betting_pool_idea")
    search_queries = state.get("evidence_search_queries")
    evidence_list = []

    search_sys_msg = SystemMessage(
        content=f"""You are a search assistant that finds and summarizes relevant evidence.
        For the given search query, return information from reliable sources.
        
        BETTING CONTEXT:
        What users are betting on: {betting_pool.get("betting_pool_idea")}
        
        Options: {betting_pool.get("options")}
        
        Your response must be a JSON object with these fields and nothing else:
        {{
            "url": "source URL",
            "summary": "brief summary of relevant information from the source",
            "search_query": "the search query that found this evidence"
        }}
        
        Guidelines:
        - Only include sources that are directly relevant
        - Summarize the key points in 2-3 sentences
        - Prefer recent sources from reputable outlets
        """
    )

    structured_llm = big_llm.with_structured_output(Evidence)

    for query in search_queries:
        search_user_msg = HumanMessage(
            content=f"""
            SEARCH QUERY: {query}

            Please find and analyze relevant evidence for this query in the context of the betting pool.
            """
        )

        try:
            # use llm to gather evidence
            # result = structured_llm.invoke([search_sys_msg, search_user_msg])
            # if not result.search_query:
            #     result.search_query = query
            # evidence_list.append(result)

            # use tavily to gather evidence
            search_docs = tavily_search.invoke(query)
            for doc in search_docs:
                search_user_msg = HumanMessage(
                    content=f"""
                    SEARCH QUERY: {query}
                    
                    SOURCE URL: {doc.get('url', '')}
                    CONTENT: {doc.get('content', '')}

                    Please analyze and summarize this search result in the context of the betting pool.
                    """
                )
                result = structured_llm.invoke([search_sys_msg, search_user_msg])
                if not result.search_query:
                    result.search_query = query
                evidence_list.append(result)
        except Exception as e:
            print(f"Error processing query '{query}': {e}")
            continue

    print(f"Evidence list: {evidence_list}")
    return {"evidence": evidence_list}


def grade_betting_pool_idea(state: BettingPoolIdeaGraderGraphOutput):
    """Grade the betting pool idea"""

    print("Grading betting pool idea")
    betting_pool = state.get("betting_pool_idea")
    print(f"betting_pool in grade_betting_pool_idea: {betting_pool}")

    # Gather evidence first
    evidence_list = state.get("evidence")

    grading_sys_msg = SystemMessage(
        content=f"""
    You are a betting pool idea grader with expertise in data analysis and probability assessment.
    
    Your task is to:
    1. Understand the EXACT time period being asked about in the question
    2. Determine if that time period has already passed, regardless of the pool's decision date
    3. Review the provided evidence and evaluate its relevance and reliability
    4. Make a decision based on official/verifiable results when available
    
    IMPORTANT TIME HANDLING: 
    - First, identify the specific time period in the question (e.g., "Q1 2024", "January 2024")
    - If that time period has passed:
      * Look for official results/data for that specific period
      * If official results are available, use them to make a decision regardless of the pool's decision date
      * If official results aren't available yet, return "not resolved yet"
    - If the time period hasn't passed yet:
      * Always return "not resolved yet"
      * Analyze the time period to determine the next date and time to check for official results
    
    DECISION GUIDELINES:
    - Return "option A" or "option B" if:
      * The time period has passed AND
      * Official results are available AND
      * The evidence clearly shows which option is correct
    - Return "not resolved yet" if:
      * The time period hasn't passed yet OR
      * Official results aren't available yet
    - Return "push" if:
      * The time period has passed AND
      * Official results show neither option is correct
    
    EVIDENCE EVALUATION:
    - Prioritize official company reports/announcements
    - Consider reliable third-party verification
    - Require multiple sources for confirmation
    - Check source dates to ensure they cover the correct time period
    
    Your response must be ONLY a JSON object with these fields:
    {{
        "result": "", // "not resolved yet", "option A", "option B", or "push"
        "probabilities": {{
            // Probabilities for each option
        }},
        "sources": [
            // URLs of sources used
        ],
        "explanation": "", // Include the time period analysis in your explanation
        "time_period_analysis": {{ 
            "period_mentioned": "", // e.g., "Q1 2024"
            "period_has_passed": true/false,
            "official_results_available": true/false
        }}
    }}
    """
    )

    grading_user_msg = HumanMessage(
        content=f"""
    EVIDENCE PROVIDED:
    {evidence_list}

    BETTING POOL DETAILS:
    Question: {betting_pool['betting_pool_idea']}
    Options: {betting_pool['options']}
    
    Option A corresponds to: {betting_pool['options'][0]}
    Option B corresponds to: {betting_pool['options'][1]}
    
    CLOSURE CRITERIA:
    {betting_pool['closure_criteria']}
    
    CLOSURE INSTRUCTIONS:
    {betting_pool['closure_instructions']}
    
    CLOSURE DATETIME: {datetime.fromtimestamp(betting_pool['closure_datetime']).strftime('%Y-%m-%d %H:%M:%S')}

    CURRENT DATETIME: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    """
    )

    # TODO Later we'll want to use Claude sonnet here, but not until after we reduce costs
    structured_llm = big_llm.with_structured_output(BettingPoolIdeaGraderOutput)
    result = structured_llm.invoke([grading_sys_msg, grading_user_msg])
    print("Grading result:", result)

    # Determine the result code based on the grading output
    if result.result == "not resolved yet":
        result_code = 0  # NOT READY TO GRADE
        # Then set the next check date and time
    elif result.result == "option A":
        result_code = 1  # is option A
    elif result.result == "option B":
        result_code = 2  # is option B
    elif result.result == "push":
        result_code = 3  # is DRAW
    else:
        result_code = 4  # is ERROR

    return {
        "betting_pool_idea_result": {
            "result": result.result,
            "result_code": result_code,
            "probabilities": result.probabilities,
            "sources": result.sources,
            "explanation": result.explanation,
            "time_period_analysis": result.time_period_analysis,
        }
    }


betting_pool_idea_grader = StateGraph(BettingPoolIdeaGraderGraphOutput)

betting_pool_idea_grader.add_node(
    "generate_evidence_queries", generate_evidence_queries
)
betting_pool_idea_grader.add_node("gather_evidence", gather_evidence)
betting_pool_idea_grader.add_node("grade_betting_pool_idea", grade_betting_pool_idea)

betting_pool_idea_grader.add_edge(START, "generate_evidence_queries")
betting_pool_idea_grader.add_edge("generate_evidence_queries", "gather_evidence")
betting_pool_idea_grader.add_edge("gather_evidence", "grade_betting_pool_idea")
betting_pool_idea_grader.add_edge("grade_betting_pool_idea", END)

betting_pool_idea_grader_agent = betting_pool_idea_grader.compile()
