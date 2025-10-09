import os
import json
import re
import requests
from fastapi import HTTPException
from groq import Groq
from dotenv import load_dotenv
from ..schemas import Proposal, Section
from typing import List, Dict
from ..core.config import settings
from json_repair import repair_json

load_dotenv()

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com"
)

from .diagram_agent import diagram_agent

class ContentAgent:
    def generate_proposal_draft(self, proposal: Proposal) -> List[Dict]:
        if not client:
            return []

        prompt = f"""
        As an expert business proposal strategist and content creator, your goal is to craft a highly detailed, comprehensive, and persuasive proposal. The tone should be professional, confident, and client-focused, demonstrating a deep understanding of their needs and our solutions.

        **Client:** {proposal.clientName}
        **Company:** {proposal.companyName}
        **Request for Proposal (RFP):** ```{proposal.rfpText}```

        **Instructions:**
        1.  Structure the proposal into **well-defined, in-depth sections**. Each section should be rich in detail, providing clear explanations, benefits, and strategic insights. Mandatory sections include:
            *   **Executive Summary:** A compelling overview of the client's challenge, our solution, and the expected ROI.
            *   **Product Overview:** Detailed description of the product/service and its functionalities.
            *   **Key Features:** Elaborate on the most important features and their value.
            *   **User Journey / Workflow:** A detailed textual description of user interaction, suitable for generating a flowchart.
            *   **Technology Stack:** List of all key technologies and why they were chosen.
            *   **Development Plan & Payment Milestones:** A phased development plan with deliverables and payment milestones in an HTML table.
            *   **Product Cost & Pricing Breakdown:** A transparent cost breakdown in an HTML table.
            *   **Timeline & Roadmap:** A detailed project timeline description, suitable for generating a Gantt chart.
            *   **About Us:** A compelling overview of our company.
            *   **Next Steps / Call to Action:** Clear next steps for the client.

        2.  For **tables**, use proper **HTML tables** (`<table>...</table>`).

        3.  Each section must be returned as a JSON object with these keys:
            - `title`: Section title (string)
            - `contentHtml`: Section content in HTML (string)
            - `image_query`: A short, descriptive query for a relevant image.

        **Output Format:**
        Return a valid JSON array of section objects, enclosed in a ```json code block.
        """

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.7,
        )

        response_content = chat_completion.choices[0].message.content
        print(f"Raw Groq API response:\n{response_content}")

        try:
            repaired_json = repair_json(response_content)
            sections_data = json.loads(repaired_json)
            if not isinstance(sections_data, list):
                return []

            processed_sections = []
            for i, section_data in enumerate(sections_data):
                image_query = section_data.get("image_query", "business technology solution")
                images = self.search_images(image_query)
                image_urls = [img["url"] for img in images[:1]] if images else []

                processed_section = {
                    "id": i,
                    "title": section_data.get("title", ""),
                    "contentHtml": section_data.get("contentHtml", ""),
                    "image_urls": image_urls,
                    "order": i + 1,
                    "image_placement": None,
                    "mermaidChart": None,
                    "layout": None,
                    "chartType": None
                }
                processed_sections.append(processed_section)

            class MockSection:
                def __init__(self, id, contentHtml):
                    self.id = id
                    self.contentHtml = contentHtml

            mock_sections = [MockSection(id=i, contentHtml=s['contentHtml']) for i, s in enumerate(processed_sections)]
            generated_charts = diagram_agent.auto_generate_charts_for_proposal(mock_sections)

            for chart in generated_charts:
                section_id = chart["section_id"]
                if 0 <= section_id < len(processed_sections):
                    processed_sections[section_id]["mermaid_chart"] = chart["chart_code"]
                    processed_sections[section_id]["chart_type"] = chart["chart_type"]

            print(f"Processed sections: {processed_sections}")
            return processed_sections
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e} on content: {response_content}")
            return []

    def enhance_section(self, content: str, action: str, tone: str) -> str:
        if not client:
            return content
        prompt = f"Perform the following action on the text below:\nAction: {action}\nTone: {tone}\n\nText: {content}"
        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error from AI service")

    def search_images(self, query: str, provider: str = "pixabay") -> List[Dict]:
        # Always use pixabay for now, as requested
        return self._search_pixabay(query)

    def _search_pixabay(self, query: str) -> List[Dict]:
        PIXABAY_API_URL = "https://pixabay.com/api/"
        params = {"key": settings.PIXABAY_API_KEY, "q": query, "image_type": "photo", "per_page": 9}
        try:
            print(f"Searching for images on Pixabay with query: {query}")
            response = requests.get(PIXABAY_API_URL, params=params)
            response.raise_for_status()
            if not response.text:
                print("Pixabay API returned an empty response.")
                return []
            data = response.json()
            print(f"Pixabay API response: {data}")
            return [{"url": hit["webformatURL"]} for hit in data.get("hits", [])]
        except requests.exceptions.RequestException as e:
            print(f"Error searching images on Pixabay: {e}")
            return []


    def generate_content_from_keywords(self, keywords: str) -> str:
        if not client:
            return "Content generation is disabled."
        prompt = f"Generate a detailed and professional proposal section based on the following keywords: {keywords}"
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content

content_agent = ContentAgent()
