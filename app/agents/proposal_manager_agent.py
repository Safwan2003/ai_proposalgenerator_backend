import os
import logging
import random
import re
import json
from json_repair import repair_json
import asyncio
from typing import List, Dict
from groq import Groq
from app.core.config import settings
from .diagram_agent import DiagramAgent
from .content_writer_agent import content_writer_agent
from app.schemas import Proposal
from sqlalchemy.ext.asyncio import AsyncSession
from .base_agent import ConversableAgent
from app import crud, schemas

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class ProposalManagerAgent(ConversableAgent):
    """AI-powered agent for managing the proposal generation process."""

    def __init__(self):
        super().__init__(
            name="ProposalManager",
            system_message="You are a proposal manager. Your task is to orchestrate the generation of a business proposal by collaborating with other agents.",
            client=client
        )

    async def generate_section_content_async(self, db: AsyncSession, section_id: int):
        """Generates content for a specific section asynchronously and updates the database."""
        logging.info(f"--- Starting async content generation for section_id: {section_id} ---")
        try:
            section = await crud.get_section(db, section_id)
            if not section:
                logging.error(f"Section {section_id} not found for content generation.")
                return

            proposal = await crud.get_proposal(db, section.proposal_id)
            if not proposal:
                logging.error(f"Proposal {section.proposal_id} not found for section {section_id}.")
                return

            prompt = f"""
            Generate the content for the section titled '{section.title}' within the context of this proposal:
            **Client:** {proposal.get('clientName')}
            **Company:** {proposal.get('companyName')}
            **RFP:** ```{proposal.get('rfpText')}```
            The content should be detailed, professional, and formatted in HTML (`<p>`, `<ul>`, `<strong>`, etc.).
            """

            message_history = [{"role": "user", "content": prompt}]
            generated_content = await asyncio.to_thread(self.generate_response, message_history)

            # Update the section with the generated content
            section_update = schemas.SectionUpdate(contentHtml=generated_content)
            await crud.update_section(db, section_id, section_update)
            logging.info(f"--- Finished async content generation for section_id: {section_id} ---")

        except Exception as e:
            logging.error(f"Error during async content generation for section {section_id}: {e}")
            # Optionally, update the section to indicate an error
            error_message = "<p>Error generating content. Please try again.</p>"
            section_update = schemas.SectionUpdate(contentHtml=error_message)
            await crud.update_section(db, section_id, section_update)

    async def generate_proposal_draft(self, proposal: Proposal, db: AsyncSession, sections: List[str] = None) -> Dict:
        logging.info("--- Starting Proposal Generation (Optimized Flow) ---")

        # 1. Create the single, powerful prompt to generate all sections at once
        if not sections:
            sections = [
                "Executive Summary",
                "Product Vision and Overview",
                "Core Functionality and Key Features",
                "User Journey / Workflow",
                "Technology Stack",
                "Development Plan",
                "Payment Milestones",
                "Product Cost & Pricing Breakdown",
                "Timeline & Roadmap",
                "About Us",
                "Path to Partnership"
            ]

        section_list = "\n".join([f"- {section}" for section in sections])

        one_shot_prompt = f"""
        As an expert business proposal strategist, generate a complete, professional business proposal based on the following details.

        **Client:** {proposal.clientName}
        **Company:** {proposal.companyName}
        **RFP:** ```{proposal.rfpText}```

        **Instructions:**
        1.  **Generate All Sections:** Create content for all of the following mandatory sections:
            {section_list}
        2.  **Content & Formatting:** The `contentHtml` must be well-structured, using paragraphs (`<p>`), lists (`<ul>`, `<ol>`), and bold text (`<strong>`) to improve readability. For sections requiring tables (like "Payment Milestones" or "Product Cost"), the content MUST be a detailed HTML `<table>`.
        3.  **Output Format:** Return a single, valid JSON array inside a ```json ... ``` block. Each object in the array must represent a section and have the keys "title" (string) and "contentHtml" (string).
        4.  **Tone:** The tone must be professional, confident, and persuasive.
        5.  **Content Quality:** The content must be detailed, well-written, and directly address the RFP.
        """

        # 2. Call the LLM once to get all section content
        logging.info("--- Generating all section content in a single pass ---")
        message_history = [{"role": "user", "content": one_shot_prompt}]
        response_text = await asyncio.to_thread(self.generate_response, message_history)

        # 3. Parse the JSON response
        try:
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if not json_match:
                # Fallback if the ```json``` block is missing, try to repair the whole string
                logging.warning("JSON block not found in LLM response, attempting to repair the full response.")
                repaired_json_str = repair_json(response_text)
            else:
                repaired_json_str = repair_json(json_match.group(1))
            
            generated_sections_data = json.loads(repaired_json_str)
            logging.info(f"Successfully parsed {len(generated_sections_data)} sections from single-pass generation.")
        except (json.JSONDecodeError, IndexError) as e:
            logging.error(f"Failed to parse JSON response from LLM: {e}")
            logging.error(f"LLM Response Text: {response_text}")
            raise ValueError("Failed to generate proposal content. The AI model returned an invalid format.")

        # 4. Post-processing
        processed_sections = []
        full_proposal_content = ""

        # First, build the full content string for context-dependent tasks
        for section_data in generated_sections_data:
            full_proposal_content += f"\n\n## {section_data.get('title', '')}\n\n{section_data.get('contentHtml', '')}"

        logging.info("--- Starting post-processing (Diagrams, Images, Tech Logos) ---")
        
        # Create async tasks for post-processing each section
        post_processing_tasks = []
        for i, section_data in enumerate(generated_sections_data):
            post_processing_tasks.append(
                self.process_single_section(i, section_data, proposal, full_proposal_content, db)
            )
        
        processed_sections = await asyncio.gather(*post_processing_tasks)

        logging.info("--- Proposal Generation Complete (Optimized Flow) ---")
        return {"sections": processed_sections}

    async def process_single_section(self, i: int, section_data: Dict, proposal: Proposal, full_proposal_content: str, db: AsyncSession) -> Dict:
        section_title = section_data.get("title", f"Section {i+1}")
        content_html = section_data.get("contentHtml", "<p>Error: Content not generated.</p>")

        section_obj = {
            "title": section_title,
            "contentHtml": content_html,
            "image_urls": [],
            "image_placement": None,
            "mermaid_chart": None,
            "chart_type": None,
            "tech_logos": [],
        }

        title_lower = section_title.lower()

        # A. Generate Diagram with smart chart type detection
        try:
            chart_type = None
            if any(term in title_lower for term in ["user journey", "workflow", "process", "architecture"]):
                chart_type = "flowchart"
            elif any(term in title_lower for term in ["development plan", "schedule"]):
                chart_type = "gantt"
            elif any(term in title_lower for term in ["system", "integration", "api"]):
                chart_type = "sequence"
            elif any(term in title_lower for term in ["structure", "organization", "hierarchy"]):
                chart_type = "mindmap"
            if "distribution" in title_lower or "breakdown" in title_lower:
                chart_type = "pie"
            
            # Prevent pie chart generation for cost/pricing sections which already generate HTML tables
            if chart_type == "pie" and any(term in title_lower for term in ["cost", "pricing"]):
                logging.info(f"Skipping pie chart generation for '{section_title}' as it's a cost/pricing section.")
                chart_type = None

            if chart_type:
                logging.info(f"Generating {chart_type} chart for section: {section_title}")
                # Instantiate DiagramAgent locally
                local_diagram_agent = DiagramAgent(client=client)
                chart_code = await asyncio.to_thread(
                    local_diagram_agent.generate_chart,
                    chart_type,
                    content_html
                )
                if chart_code:
                    section_obj["mermaid_chart"] = chart_code
                    section_obj["chart_type"] = chart_type
                    logging.info(f"Successfully generated {chart_type} chart for {section_title}")
                else:
                    logging.warning(f"Failed to generate {chart_type} chart for {section_title}")
        except Exception as e:
            logging.error(f"Error generating chart for section {section_title}: {e}")

        # B. Analyze for Tech Logos
        if "technology stack" in title_lower:
            section_obj["tech_logos"] = await content_writer_agent.analyze_tech_stack(proposal.rfpText, full_proposal_content, db)

        # C. Search for Images
        if not any(keyword in title_lower for keyword in ["user journey", "workflow", "technology stack", "about us", "company", "logo", "payment milestone", "cost", "pricing", "development plan"]):
            try:
                content_keywords = await asyncio.to_thread(self.get_image_query_from_text, content_html)
                image_query = f"{section_title}{content_keywords}{proposal.rfpText}".strip()[:100]
                if image_query:
                    logging.info(f"Searching for image with query: {image_query}")
                    images = await content_writer_agent.search_images(image_query)
                    if images:
                        section_obj["image_urls"] = [images[0]["url"]]
                        section_obj["image_placement"] = "full-width-top"
            except Exception as e:
                logging.error(f"Error searching for image for section {section_title}: {e}")

        logging.info(f"Processed section {i+1}: Title: {section_title}")
        return section_obj

    async def enhance_section_content(self, content: str, enhancement_type: str) -> str:
        """Enhances the content of a section using an AI agent."""
        logging.info(f"--- Enhancing section content with type: {enhancement_type} ---")
        
        prompt = f"""
        Please enhance the following text based on the instruction: '{enhancement_type}'.
        Return only the enhanced text, without any additional commentary.
        The text should be in HTML format.

        Original Text:
        ---
        {content}
        ---
        """

        message_history = [{"role": "user", "content": prompt}]
        enhanced_content = await asyncio.to_thread(self.generate_response, message_history)
        
        logging.info("--- Section content enhancement complete ---")
        return enhanced_content


# Singleton instance for import
proposal_manager_agent = ProposalManagerAgent()