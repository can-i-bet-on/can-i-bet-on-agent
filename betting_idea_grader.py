from datetime import datetime
import os
from typing import Literal, Optional
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langchain_community.tools.tavily_search import TavilySearchResults

from betting_pool_generator import BettingPoolGeneratorOutput

class EvidenceSearchQueries(BaseModel):
    evidence_search_queries: list[str]


class BettingPoolIdeaGraderOutput(BaseModel):
    
    result: str  # Required
    probabilities: Optional[dict[str, float]] = None
    sources: list[str]
    explanation: str
    time_period_analysis: dict


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


# perplexity_llm = ChatPerplexity(
#     model="sonar-reasoning",
#     temperature=0.7,
#     api_key=os.getenv("PPLX_API_KEY")
# )

perplexity_llm = ChatOpenAI(
    base_url="https://api.perplexity.ai",
    model="sonar-pro",
    temperature=0,
    api_key=os.getenv("PPLX_API_KEY"),
    # headers={
    #     "Authorization": f"Bearer {os.getenv('PPLX_API_KEY')}"
    # }
)

openai_llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
)

tavily_search = TavilySearchResults(max_results=2)

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

    structured_llm = openai_llm.with_structured_output(EvidenceSearchQueries)
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
    
    structured_llm = perplexity_llm.with_structured_output(Evidence)
    
    for query in search_queries:
        search_user_msg = HumanMessage(
            content=f"""
            SEARCH QUERY: {query}

            Please find and analyze relevant evidence for this query in the context of the betting pool.
            """
        )
        
        try:
            # use llm to gather evidence
            result = structured_llm.invoke([search_sys_msg, search_user_msg])
            if not result.search_query:
                result.search_query = query
            evidence_list.append(result)

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
    return {
        "evidence": evidence_list
    }

    # Then use the Perplexity API or Tavily to run the search queries.
    # Load the results from the searches into JSON and XML
    # Add these results to the state, then...
    
    # Separate function (would call this in parallel for a chunk of articles)
    # Ask the LLM to count the number of records that support the "Yes wins" criteria. Ask it to explain why it chose yes (but you don't have to record it, CoT)
    # Ask the LLM to count the number of records that support the "No wins" criteria. Ask it to explain why it chose yes (but you don't have to record it, CoT)
    # Ask the LLM to count the number of records that are "Unknown". Ask it to explain why it chose yes (but you don't have to record it, CoT)
    # If it finds an equal number of sources, don't close
    # If it can't find at least 2 sources to support an outcome, don't close
    # If it find one outweighs the other, close (ideally with a tool call to close the pool on the contract

def grade_betting_pool_idea(state: BettingPoolIdeaGraderGraphOutput):
    """Grade the betting pool idea"""
    
    print("Grading betting pool idea")
    betting_pool = state.get("betting_pool_idea")
    print(f"betting_pool in grade_betting_pool_idea: {betting_pool}")
    
    # Gather evidence first
    evidence_list = state.get("evidence")
    
    grading_sys_msg = SystemMessage(content=f"""
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
    """)

    grading_user_msg = HumanMessage(content=f"""
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
    """)

    structured_llm = perplexity_llm.with_structured_output(BettingPoolIdeaGraderOutput)
    result = structured_llm.invoke([grading_sys_msg, grading_user_msg])
    print("Grading result:", result)

    # Determine the result code based on the grading output
    if result.result == "not resolved yet":
        result_code = 0  # NOT READY TO GRADE
    elif result.result == "option A":
        result_code = 1  # is option A
    elif result.result == "option B":
        result_code = 2  # is option B
    elif result.result == "push":
        result_code = 3  # is DRAW
    else:
        result_code = 4  # is ERROR

    return {
        'betting_pool_idea_result': {
            'result': result.result,
            'result_code': result_code,
            'probabilities': result.probabilities,
            'sources': result.sources,
            'explanation': result.explanation,
            'time_period_analysis': result.time_period_analysis
        }
    }


def grade_betting_pool_idea2(betting_pool):
    """Grade the betting pool idea"""
    
    print("Grading betting pool idea")
    
    print(f"betting_pool in grade_betting_pool_idea: {betting_pool}")
    
    grading_sys_msg = SystemMessage(content=f"""
    You are a betting pool idea grader with expertise in data analysis and probability assessment.
    
    Your task is to:
    1. Understand the EXACT question and its closure criteria, closure instructions, and closure date
    2. Assign probabilities that reflect your confidence in each option
    3. Always choose the highest probability option as the result
    
    IMPORTANT: 
    - CAREFULLY COMPARE THE EXACT DATE AND TIME:
      * Past events: closure datetime is EARLIER than current datetime (compare both date AND time components)
      * Future events: closure datetime is LATER than current datetime (compare both date AND time components)
    - For past events (where closure time has passed), if you're not 100% certain of the outcome, distribute probabilities based on your confidence
    - For past events, it should NEVER return "not resolved yet" as a result
    - For future events (where closure time has not yet passed), return "not resolved yet" as a result and probabilities of 0 for all options and an empty list of sources
    - For future events that cannot be determined yet, return "not resolved yet" as a result and probabilities of 0 for all options and an empty list of sources
    - The result must be the option with the highest probability
    - All probabilities must sum to exactly 1.0 for past events and 0 for future events
    - You MUST include ALL sources used to reach your conclusion in the sources list
    - Prefer sources that:
      * Are from reputable news organizations or official websites
      * Directly address the question
      * Have recent updates relevant to the closure date
      * Provide verifiable data or official statements

    Grading guidelines:
    - High probability (>0.6): Strong evidence for this option
    - Medium probability (0.3-0.6): Some evidence or reasonable likelihood
    - Low probability (<0.3): Less likely but still possible
    - Only assign 1.0 if you have absolute certainty of the outcome
    - When sources disagree, distribute probabilities to reflect the relative strength and reliability of each source
    - If neither option A nor option B is the result, return "push" as the result.

    Your response must be ONLY a JSON object. Do not include any explanatory text, markdown formatting, or code blocks:
    {{
        "result": "", // the option with highest probability or "push"
        "probabilities": {{
            // Assign each option a probability between 0.01 and 1.0
            // Probabilities MUST sum to exactly 1.0 for past events and 0 for future events
            // Use the exact option names as provided
        }},
        "sources": [
            // List the URLs of sources that directly address the question
            // Only include sources that provided relevant information
        ],
        "explanation": "", // Detailed explanation of your reasoning, citing specific evidence from sources
    }}
    """)

    grading_user_msg = HumanMessage(content=f"""
    BETTING POOL DETAILS:
    Question: {betting_pool['betting_pool_idea']}
    Options: {betting_pool['options']}
    
    CLOSURE SUMMARY:
    {betting_pool['closure_summary']}
    
    CLOSURE INSTRUCTIONS:
    {betting_pool['closure_instructions']}
    
    CLOSURE DATETIME: {betting_pool['closure_datetime']}

    CURRENT DATETIME: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    """)

    structured_llm = perplexity_llm.with_structured_output(BettingPoolIdeaGraderOutput)
    result = structured_llm.invoke([grading_sys_msg, grading_user_msg])
    print("Grading result:", result)

    # Determine the result based on the grading output
    if result.result == "not resolved yet":
        return 0  # NOT READY TO GRADE
    elif result.result == "option A":
        return 1  # is option A
    elif result.result == "option B":
        return 2  # is option B
    elif result.result == "push":
        return 3  # is DRAW
    else:
        return 4  # is ERROR

    return {
        "result": result.result,
        "probabilities": result.probabilities,
        "sources": result.sources,
        "explanation": result.explanation
    }

betting_pool_idea_grader = StateGraph(BettingPoolIdeaGraderGraphOutput)

betting_pool_idea_grader.add_node("generate_evidence_queries", generate_evidence_queries)
betting_pool_idea_grader.add_node("gather_evidence", gather_evidence)
betting_pool_idea_grader.add_node("grade_betting_pool_idea", grade_betting_pool_idea)

betting_pool_idea_grader.add_edge(START, "generate_evidence_queries")
betting_pool_idea_grader.add_edge("generate_evidence_queries", "gather_evidence")
betting_pool_idea_grader.add_edge("gather_evidence", "grade_betting_pool_idea")
betting_pool_idea_grader.add_edge("grade_betting_pool_idea", END)

betting_pool_idea_grader_agent = betting_pool_idea_grader.compile()