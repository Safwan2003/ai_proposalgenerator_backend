import os
import json
import re
import random
import requests
import logging
from typing import List, Dict
from app.schemas import Proposal
from json_repair import repair_json
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import crud

# Initialize Groq client
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com"
)


class ContentAgent:
    """AI-powered content generation agent for premium business proposals."""

    def __init__(self):
        self.simple_icons_data = self._load_simple_icons_data()

    def _load_simple_icons_data(self):
        try:
            url = "https://cdn.jsdelivr.net/npm/simple-icons@latest/_data/simple-icons.json"
            response = requests.get(url)
            response.raise_for_status()
            # Correctly access the list of icons within the JSON structure
            return response.json().get("icons", [])
        except Exception as e:
            logging.error(f"Error loading simple-icons data: {e}")
            return []

    def generate_proposal_draft(self, proposal: Proposal) -> List[Dict]:
        """Generate a complete proposal draft with structured sections, diagrams, and design hints."""
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
        - Use HTML tables for pricing and milestones.
        - Keep tone: professional, elegant, confident, and client-centered.
        """

        # ---------------------- LLM REQUEST ----------------------
        try:
            resp = client.chat.completions.create(
                model=os.getenv("GROQ_DEFAULT_MODEL_NAME", "llama-3.1-8b-instant"),
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            response_content = resp.choices[0].message.content
            logging.debug(f"Raw Groq API response: {response_content}")

            repaired_json = repair_json(response_content)
            sections_data = json.loads(repaired_json)
        except Exception as e:
            logging.error(f"Error generating proposal draft from LLM: {e}")
            return []

        if not isinstance(sections_data, list):
            logging.error("Model output is not a valid JSON list.")
            return []

        # ---------------------- SECTION PROCESSING ----------------------
        processed_sections = []

        for i, section_data in enumerate(sections_data):
            title = section_data.get("title", f"Section {i+1}")
            content_html = section_data.get("contentHtml", "")
            image_query = section_data.get("image_query", "business technology")

            section_obj = {
                "id": i,
                "title": title,
                "contentHtml": content_html,
                "image_urls": [],
                "order": i + 1,
                "image_placement": None,
                "mermaid_chart": None,
                "chart_type": None,
                "tech_logos": [],
            }

            # --- Handle Technology Stack Section ---
            should_search_pixabay = True
            lower_title = title.lower()

            if "technology" in lower_title or "tech stack" in lower_title:
                logging.info(f"Processing Technology Stack section: {title}")
                should_search_pixabay = False

                techs = self.extract_technologies_from_content(content_html)
                logos = []

                for tech in techs:
                    name = None
                    slug = None
                    if isinstance(tech, dict):
                        name = tech.get("name")
                        slug = tech.get("slug")
                    elif isinstance(tech, list) and len(tech) == 2:
                        name, slug = tech

                    if slug:
                        logo_url = self.get_logo_url_for_tech(slug)
                        logos.append({"name": name or slug, "logo_url": logo_url})

                section_obj["tech_logos"] = logos
                section_obj["image_urls"] = []  # No Pixabay image for tech stack
                section_obj["image_placement"] = None
            elif "about us" in lower_title or "company" in lower_title or "logo" in lower_title or "development plan" in lower_title or "payment milestone" in lower_title or "user journey" in lower_title or "workflow" in lower_title:
                logging.info(f"Skipping Pixabay search for section: {title}")
                should_search_pixabay = False
                section_obj["image_urls"] = []
                section_obj["image_placement"] = None

            if should_search_pixabay:
                imgs = self.search_images(image_query)
                if imgs:
                    section_obj["image_urls"] = [imgs[0]["url"]]
                    section_obj["image_placement"] = random.choice(["full-width-top", "full-width-bottom"])
                else:
                    section_obj["image_urls"] = []
                    section_obj["image_placement"] = None

            processed_sections.append(section_obj)

        # ---------------------- DIAGRAM GENERATION ----------------------
        class MockSection:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        mock_sections = [MockSection(**s) for s in processed_sections]
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
        params = {
            "key": settings.PIXABAY_API_KEY,
            "q": query,
            "image_type": "photo",
            "per_page": 9,
        }
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

    def extract_technologies_from_content(self, html: str) -> List[Dict[str, str]]:
        """Extract technology names and their Simple Icons slugs using LLM."""
        if not client:
            return []

        text = re.sub(r"<[^>]+>", " ", html or "")
        prompt = f"""
        Analyze the following text from a technology stack description.
        Identify all distinct technologies mentioned and their corresponding Simple Icons slugs (from simpleicons.org).
        It is CRUCIAL that you return a VALID JSON array of objects. Each object MUST have a "name" (string) and a "slug" (string).
        The slug MUST be a valid Simple Icons slug (e.g., "Node.js" -> "nodedotjs", "React" -> "react").
        If a technology does not have a clear Simple Icons slug, omit it.

        Text: "{text}"

        Example Output:
        ```json
        [
          {{ "name": "React", "slug": "react" }},
          {{ "name": "Node.js", "slug": "nodedotjs" }},
          {{ "name": "PostgreSQL", "slug": "postgresql" }}
        ]
        ```
        """
        retries = 3
        for i in range(retries):
            try:
                resp = client.chat.completions.create(
                    model=os.getenv("GROQ_DEFAULT_MODEL_NAME", "llama-3.1-8b-instant"),
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = resp.choices[0].message.content
                logging.debug(f"Raw LLM response for extract_technologies_from_content (attempt {i+1}): {response_text}")
                technologies = json.loads(repair_json(response_text))
                valid_techs = []
                for tech in technologies:
                    name = tech.get("name")
                    slug = tech.get("slug")
                    if not name or not slug or not isinstance(name, str) or not isinstance(slug, str):
                        logging.warning(f"Skipping malformed technology entry from LLM: {tech}")
                        continue
                    valid_techs.append({"name": name, "slug": slug})
                return valid_techs
            except json.JSONDecodeError as json_e:
                logging.warning(f"LLM response was not valid JSON (attempt {i+1}): {json_e}")
                if i == retries - 1:
                    logging.error(f"Failed to extract technologies after {retries} attempts due to JSON decoding error.")
                    return []
            except Exception as e:
                logging.error(f"Error extracting technologies with LLM (attempt {i+1}): {e}")
                if i == retries - 1:
                    logging.error(f"Failed to extract technologies after {retries} attempts.")
                    return []
        return [] # Should not be reached

    # ------------------------------------------------------------------

    def get_logo_url_for_tech(self, tech_slug: str) -> str:
        """Return a Simple Icons CDN URL for the given tech slug."""
        if not tech_slug:
            return ""
        return f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{tech_slug}.svg"

    def search_tech_logos(self, db: Session, query: str) -> List[Dict]:
        """Search for tech logos from both custom DB and Simple Icons with a unified, tiered approach."""
        if not query:
            return []

        try:
            lower_query = query.lower()
            custom_logos = crud.get_custom_logos(db)
            simple_icons = self.simple_icons_data

            # --- Tier 1: Search Custom Logos ---
            custom_matches = []
            for logo in custom_logos:
                if lower_query in logo.name.lower():
                    custom_matches.append({"name": logo.name, "logo_url": logo.logo_url})

            # --- Tier 2: Search Simple Icons ---
            exact_matches = []
            starts_with_matches = []
            substring_matches = []
            
            # Use a set of names to avoid duplicates from Simple Icons
            found_names = {logo["name"] for logo in custom_matches}

            for icon in simple_icons:
                if not isinstance(icon, dict):
                    continue

                title = icon.get("title")
                slug = icon.get("slug")

                if not title or not slug or title in found_names:
                    continue
                
                result_item = {"name": title, "logo_url": self.get_logo_url_for_tech(slug)}
                lower_title = title.lower()

                if lower_title == lower_query:
                    exact_matches.append(result_item)
                    found_names.add(title)
                elif lower_title.startswith(lower_query):
                    starts_with_matches.append(result_item)
                    found_names.add(title)
                elif lower_query in lower_title:
                    substring_matches.append(result_item)
                    found_names.add(title)

            # --- Combine all results ---
            final_results = custom_matches + exact_matches + starts_with_matches + substring_matches
            
            logging.info(f"Unified tech logo search for '{query}' found {len(final_results)} results.")
            return final_results

        except Exception as e:
            logging.error(f"Error in unified tech logo search for '{query}': {e}")
            return []


# Singleton instance for import
content_agent = ContentAgent()
