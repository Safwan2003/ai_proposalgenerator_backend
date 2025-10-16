import os
import json
import re
import random
import requests
import logging
from typing import List, Dict
from fastapi import HTTPException
from dotenv import load_dotenv
from groq import Groq
from json_repair import repair_json

from ..schemas import Proposal, Section
from ..core.config import settings
from .diagram_agent import diagram_agent

load_dotenv()

# Initialize Groq client
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com"
)


class ContentAgent:
    """AI-powered content generation agent for premium business proposals."""

    def generate_proposal_draft(self, proposal: Proposal) -> List[Dict]:
        """
        Generate a complete proposal draft with structured sections, diagrams, and design hints.
        """
        if not client:
            logging.error("Groq client not initialized — missing API key.")
            return []

        prompt = f"""
        As an expert business proposal strategist and content creator, your task is to craft a
        highly detailed, persuasive, and visually structured proposal for a corporate client.

        **Client:** {proposal.clientName}
        **Company:** {proposal.companyName}
        **RFP:** ```{proposal.rfpText}```

        **Mandatory Sections:**
        - Executive Summary
        - Product Overview
        - Key Features
        - User Journey / Workflow
        - Technology Stack
        - Development Plan & Payment Milestones
        - Product Cost & Pricing Breakdown
        - Timeline & Roadmap
        - About Us
        - Next Steps / Call to Action

        **Formatting & Output Rules:**
        - Return a valid JSON array enclosed in ```json``` block.
        - Each section must have:
            * title (string)
            * contentHtml (string, valid HTML)
            * image_query (short image description)
            * design_hints: {{ "layout_type": "standard-text", "visual_tone": "professional" }}
        - Use HTML tables for pricing and milestones.
        - Keep tone: professional, elegant, confident, and client-centered.
        """

        try:
            resp = client.chat.completions.create(
                model=os.getenv("GROQ_DEFAULT_MODEL_NAME", "llama-3.1-8b-instant"),
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            response_content = resp.choices[0].message.content
            print(f"Raw Groq API response:\n{response_content}")

            repaired_json = repair_json(response_content)
            sections_data = json.loads(repaired_json)
            if not isinstance(sections_data, list):
                logging.error("Model output is not a valid JSON list.")
                return []

            processed_sections = []
            for i, section_data in enumerate(sections_data):
                title = section_data.get("title", f"Section {i+1}")
                content_html = section_data.get("contentHtml", "")
                image_query = section_data.get("image_query", "business technology")

                # Skip diagram-related image searches
                if title in ["User Journey / Workflow", "Development Plan & Payment Milestones", "Timeline & Roadmap"]:
                    images = []
                    placement = None
                else:
                    imgs = self.search_images(image_query)
                    placement = random.choice(["full-width-top", "full-width-bottom"]) if imgs else None
                    images = [{"url": imgs[0]["url"], "alt": image_query, "placement": placement}] if imgs else []

                section_obj = {
                    "id": i,
                    "title": title,
                    "contentHtml": content_html,
                    "images": images,
                    "order": i + 1,
                    "image_placement": placement,
                    "mermaid_chart": None,
                    "chart_type": None,
                    "tech_logos": [],
                    "design_hints": section_data.get("design_hints", {"layout_type": "standard-text", "visual_tone": "professional"}),
                }

                # Extract tech logos for "Technology Stack"
                if title.lower().startswith("technology"):
                    tech_names = self.extract_technologies_from_content(content_html)
                    logos = []
                    for tech in tech_names:
                        logo_url = self.get_logo_url_for_tech(tech)
                        if logo_url:
                            logos.append({"name": tech, "logo_url": logo_url})
                    section_obj["tech_logos"] = logos

                processed_sections.append(section_obj)

            # Generate diagrams using Diagram Agent
            mock_sections = [type("MockSection", (), s) for s in processed_sections]
            charts = diagram_agent.auto_generate_charts_for_proposal(mock_sections)

            allowed_sections = ["User Journey / Workflow", "Development Plan & Payment Milestones"]
            for chart in charts:
                sid = chart["section_id"]
                if 0 <= sid < len(processed_sections):
                    title = processed_sections[sid]["title"]
                    if title in allowed_sections:
                        processed_sections[sid]["mermaid_chart"] = chart["chart_code"]
                        processed_sections[sid]["chart_type"] = chart["chart_type"]

            return processed_sections

        except Exception as e:
            logging.error(f"Error generating proposal draft: {e}")
            return []

    # ------------------------------------------------------------------

    def enhance_section(self, content: str, action: str, tone: str) -> str:
        """Modify or re-tone an existing section of content."""
        if not client:
            return content

        prompt = f"""
        Perform this action on the text:
        Action: {action}
        Desired Tone: {tone}

        Text:
        {content}
        """

        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logging.error(f"Error enhancing section: {e}")
            raise HTTPException(status_code=500, detail="AI enhancement failed.")

    # ------------------------------------------------------------------

    def search_images(self, query: str) -> List[Dict]:
        """Search relevant business or tech imagery via Pixabay API."""
        PIXABAY_API_URL = "https://pixabay.com/api/"
        params = {"key": settings.PIXABAY_API_KEY, "q": query, "image_type": "photo", "per_page": 9}
        try:
            print(f"Searching Pixabay for: {query}")
            res = requests.get(PIXABAY_API_URL, params=params)
            res.raise_for_status()
            data = res.json()
            hits = data.get("hits", [])
            return [{"url": h["webformatURL"]} for h in hits]
        except Exception as e:
            logging.warning(f"Pixabay image search failed: {e}")
            return []

    # ------------------------------------------------------------------

    def generate_content_from_keywords(self, keywords: str) -> str:
        """Generate new proposal text based on keywords."""
        if not client:
            return "Content generation unavailable."

        prompt = f"Generate a professional, detailed proposal section based on these keywords: {keywords}"
        resp = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
        )
        return resp.choices[0].message.content

    # ------------------------------------------------------------------

    def extract_technologies_from_content(self, html: str) -> List[str]:
        """Extract common technology names from HTML or text."""
        text = re.sub(r"<[^>]+>", " ", html or "")
        tech_keywords = [
            "React", "Next.js", "Node.js", "Express", "Django", "Flask", "MongoDB", "PostgreSQL",
            "MySQL", "AWS", "Azure", "GCP", "TensorFlow", "PyTorch", "Docker", "Kubernetes", "Redis",
            "GraphQL", "TypeScript", "JavaScript", "Python", "Java"
        ]
        return [t for t in tech_keywords if re.search(rf"\b{re.escape(t)}\b", text, re.IGNORECASE)]

    def get_logo_url_for_tech(self, tech_name: str) -> str:
        """Return logo URLs for common technologies."""
        logos = {
            "React": "https://raw.githubusercontent.com/github/explore/main/topics/react/react.png",
            "Next.js": "https://raw.githubusercontent.com/vercel/next.js/canary/docs/public/favicon/favicon.png",
            "Node.js": "https://raw.githubusercontent.com/github/explore/main/topics/nodejs/nodejs.png",
            "Docker": "https://raw.githubusercontent.com/github/explore/main/topics/docker/docker.png",
            "Kubernetes": "https://raw.githubusercontent.com/github/explore/main/topics/kubernetes/kubernetes.png",
            "AWS": "https://raw.githubusercontent.com/github/explore/main/topics/aws/aws.png",
            "GCP": "https://raw.githubusercontent.com/github/explore/main/topics/google-cloud/google-cloud.png",
            "Azure": "https://raw.githubusercontent.com/github/explore/main/topics/azure/azure.png",
            "TensorFlow": "https://raw.githubusercontent.com/github/explore/main/topics/tensorflow/tensorflow.png",
            "PyTorch": "https://raw.githubusercontent.com/github/explore/main/topics/pytorch/pytorch.png",
            "MongoDB": "https://raw.githubusercontent.com/github/explore/main/topics/mongodb/mongodb.png",
            "PostgreSQL": "https://raw.githubusercontent.com/github/explore/main/topics/postgresql/postgresql.png",
            "MySQL": "https://raw.githubusercontent.com/github/explore/main/topics/mysql/mysql.png",
            "Redis": "https://raw.githubusercontent.com/github/explore/main/topics/redis/redis.png",
            "GraphQL": "https://raw.githubusercontent.com/github/explore/main/topics/graphql/graphql.png",
            "TypeScript": "https://raw.githubusercontent.com/github/explore/main/topics/typescript/typescript.png",
            "JavaScript": "https://raw.githubusercontent.com/github/explore/main/topics/javascript/javascript.png",
            "Python": "https://raw.githubusercontent.com/github/explore/main/topics/python/python.png",
            "Java": "https://raw.githubusercontent.com/github/explore/main/topics/java/java.png",
        }

        if tech_name in logos:
            return logos[tech_name]

        safe = tech_name.replace(" ", "%20")
        return f"https://img.shields.io/badge/{safe}-logo-lightgrey?logo={safe}&logoColor=white"


# Singleton instance for import use
content_agent = ContentAgent()
