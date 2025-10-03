import os
import json
import re
import requests
from fastapi import HTTPException
from groq import Groq
from dotenv import load_dotenv
from ..schemas import Proposal
from typing import List, Dict
from ..core.config import settings

load_dotenv()

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com"
)

class ContentAgent:
    def generate_proposal_draft(self, proposal: Proposal) -> List[Dict]:
        if not client:
            return []
        """Generate a proposal draft with structured sections, tables, and images using Groq API."""

        prompt = f"""
        As an expert proposal writer, create a comprehensive and persuasive proposal based on the following details. 
        The tone should be professional, confident, and client-focused.

        **Client:** {proposal.clientName}
        **Company:** {proposal.companyName}
        **Request for Proposal (RFP):** ```{proposal.rfpText}```

        **Instructions:**
        1. Structure the proposal into **well-defined sections**. Mandatory sections include:
            * Executive Summary
            * Product Overview
            * Key Features
            * User Journey / Workflow
            * Technology Stack (Frontend, Backend, Database, Cloud, APIs, etc.)
            * Development Plan & Payment Milestones
            * Product Cost & Pricing Breakdown
            * Timeline
            * About Us
            * Next Steps / Call to Action

           You may add additional professional sections if appropriate (e.g., Risk Management, Competitive Advantage, Support & Maintenance).

        2. For **tables**, when presenting structured information (e.g., pricing, timeline, tech stack), use proper **HTML tables** (`<table><tr><td>...</td></tr></table>`). 
           Example:
           ```html
           <table>
             <tr><th>Milestone</th><th>Timeline</th><th>Payment</th></tr>
             <tr><td>Phase 1 - Design</td><td>2 weeks</td><td>20%</td></tr>
           </table>
           ```

        3. Each section must be returned as a JSON object with these keys:
            - `title`: Section title (string)
            - `contentHtml`: Section content in HTML (string, supports <h1>, <h2>, <p>, <ul>, <li>, <strong>, <table>, etc.)
            - `image_query`: Short query for a relevant image (optional)
            - `image_placement`: Suggested placement ("full-width", "inline-left", "inline-right", optional)

        **Output Format:**
        Return a valid JSON array of section objects.

        **Example:**
        ```json
        {{
            "title": "Technology Stack",
            "contentHtml": "<h2>Technology Stack</h2><table><tr><th>Layer</th><th>Technology</th></tr><tr><td>Frontend</td><td>React.js</td></tr><tr><td>Backend</td><td>FastAPI (Python)</td></tr><tr><td>Database</td><td>MySQL</td></tr></table>",
            "image_query": "software architecture diagram",
            "image_placement": "full-width"
        }}
        ```

        Generate the proposal now.
        """

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
        )

        response_content = chat_completion.choices[0].message.content

        # Extract pure JSON string from markdown code block using regex
        match = re.search(r"```json\s*(.*?)```", response_content, re.DOTALL)
        if match:
            pure_json_string = match.group(1).strip()
        else:
            pure_json_string = response_content.strip()

        try:
            sections_data = json.loads(pure_json_string)
            if not isinstance(sections_data, list):
                return []
            
            processed_sections = []
            for i, section in enumerate(sections_data):
                title = section.get("title", "")
                content_html = section.get("contentHtml", "")
                image_urls = []  # Default to no images

                # Only search for an image if the AI provided a query
                if "image_query" in section and section["image_query"]:
                    image_query = section["image_query"]
                    images = self.search_images(image_query)
                    if images:
                        image_urls = [img["url"] for img in images[:1]]

                processed_sections.append({
                    "title": title,
                    "contentHtml": content_html,
                    "images": image_urls,
                    "image_placement": section.get("image_placement"),
                    "order": i + 1
                })
            return processed_sections
        except json.JSONDecodeError:
            return []

    def enhance_section(self, content: str, action: str, tone: str) -> str:
        if not client:
            return content
        """Enhance a section using Groq API."""

        prompt = f"""Perform the following action on the text below:
        Action: {action}
        Tone: {tone}

        Text: {content}
        """

        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            raise HTTPException(status_code=500, detail="Error from AI service")

    def search_images(self, query: str, tags: str = None) -> List[Dict]:
        """Search for images using Pixabay API."""
        search_query = query
        if tags:
            search_query += f" {tags.replace(', ', ' ')}"

        PIXABAY_API_URL = "https://pixabay.com/api/"
        params = {
            "key": settings.PIXABAY_API_KEY,
            "q": search_query,
            "image_type": "photo",
            "per_page": 9
        }
        
        try:
            response = requests.get(PIXABAY_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            images = []
            for hit in data.get("hits", []):
                images.append({
                    "url": hit["webformatURL"],
                    "source": "Pixabay",
                    "attribution": hit["user"]
                })
            return images
        except requests.exceptions.RequestException as e:
            print(f"Error calling Pixabay API: {e}")
            return []

    def generate_content_from_keywords(self, keywords: str) -> str:
        if not client:
            return "Content generation is disabled because the AI service is not configured."
        """Generate content based on keywords using Groq API."""
        prompt = f"""Generate a detailed and professional proposal section based on the following keywords/description:
        Keywords: {keywords}
        """

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
        )

        return chat_completion.choices[0].message.content


content_agent = ContentAgent()
