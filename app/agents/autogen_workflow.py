import logging
from typing import Dict, Any, List

from app import schemas
from .research_agent import web_search
from .content_agent import content_agent
from .diagram_agent import diagram_agent as diagram_agent_logic
from .automation_agent import automation_agent as automation_agent_logic

# --- TOOL WRAPPERS ---

def enhance_section_wrapper(content: str, action: str, tone: str, **kwargs) -> str:
    return content_agent.enhance_section(content, action, tone)

def generate_content_for_keywords_wrapper(keywords: str) -> str:
    return content_agent.generate_content_from_keywords(keywords)

def generate_proposal_draft_wrapper(**kwargs) -> List[Dict]:
    """Wrapper for proposal draft generation. Handles dict or JSON string."""
    try:
        pydantic_proposal = schemas.Proposal.model_validate(kwargs)

        return content_agent.generate_proposal_draft(pydantic_proposal)
    except Exception as e:
        logging.error(f"generate_proposal_draft_wrapper error: {e}")
        return []

def suggest_chart_type_wrapper(content: str) -> str:
    return diagram_agent_logic.suggest_chart_type(content)

def generate_chart_wrapper(description: str, chart_type: str, **kwargs) -> str:
    if chart_type == "flowchart":
        return diagram_agent_logic.generate_flowchart(description)
    if chart_type == "gantt":
        return diagram_agent_logic.generate_gantt_chart(description)
    if chart_type == "sequence":
        return diagram_agent_logic.generate_sequence_diagram(description)
    if chart_type == "mindmap":
        return diagram_agent_logic.generate_mindmap(description)
    if chart_type == "pie":
        return diagram_agent_logic.generate_pie_chart(description)
    if chart_type == "user_journey":
        return diagram_agent_logic.generate_user_journey(description)
    if chart_type == "c4":
        return diagram_agent_logic.generate_c4_diagram(description)
    return "Unsupported chart type"

def update_chart_wrapper(modification_prompt: str, current_chart_code: str) -> str:
    return diagram_agent_logic.update_chart(modification_prompt, current_chart_code)

def fix_chart_wrapper(broken_mermaid_code: str) -> str:
    return diagram_agent_logic.fix_chart(broken_mermaid_code)

def get_smart_suggestions_wrapper(context: str) -> List[str]:
    return automation_agent_logic.get_smart_suggestions(context)

def expand_bullet_points_wrapper(bullet_points: List[str]) -> str:
    return automation_agent_logic.expand_bullet_points(bullet_points)


all_tools = {
    "web_search": web_search,
    "enhance_section": enhance_section_wrapper,
    "generate_content_for_keywords": generate_content_for_keywords_wrapper,
    "generate_proposal_draft": generate_proposal_draft_wrapper,
    "suggest_chart_type": suggest_chart_type_wrapper,
    "generate_chart": generate_chart_wrapper,
    "update_chart": update_chart_wrapper,
    "fix_chart": fix_chart_wrapper,
    "get_smart_suggestions": get_smart_suggestions_wrapper,
    "expand_bullet_points": expand_bullet_points_wrapper,
}

def run_master_workflow(tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """
    Directly calls the appropriate tool function based on the tool name.
    """
    if tool_name not in all_tools:
        raise ValueError(f"Tool '{tool_name}' not found.")

    tool_function = all_tools[tool_name]
    return tool_function(**tool_args)

