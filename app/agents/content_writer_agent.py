import os
import logging
import httpx
import asyncio
import json
from typing import List, Dict, Optional, Any
from groq import Groq
from app.core.config import settings
from .base_agent import ConversableAgent
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud
from json_repair import repair_json


# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class ContentWriterAgent(ConversableAgent):
    """AI-powered agent for writing the content of proposal sections."""

    def __init__(self, client: Groq):
        super().__init__(
            name="ContentWriter",
            system_message="You are an expert proposal writer. Your task is to write the content for a given section of a business proposal based on the provided RFP. You can also generate content for all sections at once.",
            client=client
        )

        # Extended tech name mapping with more variations and standardized slugs
        self.tech_name_map = {
            # Programming Languages
            "natural language processing": "nlp",
            "machine learning": "ml",
            "artificial intelligence": "ai",
            "javascript": "javascript",
            "typescript": "typescript",
            "python": "python",
            "java": "java",
            "c++": "cplusplus",
            "c#": "csharp",
            "ruby": "ruby",
            "php": "php",
            "go": "go",
            "rust": "rust",
            "kotlin": "kotlin",
            "swift": "swift",
            
            # Frontend Frameworks
            "react": "react",
            "angular": "angularjs",
            "vue": "vuejs",
            "svelte": "svelte",
            "next.js": "nextjs",
            "nuxt.js": "nuxtjs",
            
            # Backend Technologies
            "nodejs": "nodejs",
            "express": "express",
            "django": "django",
            "flask": "flask",
            "fastapi": "fastapi",
            "spring": "spring",
            "ruby on rails": "rails",
            
            # Web Technologies
            "html": "html5",
            "css": "css3",
            "sass": "sass",
            "less": "less",
            "bootstrap": "bootstrap",
            "tailwind css": "tailwindcss",
            "webpack": "webpack",
            
            # Databases
            "mysql": "mysql",
            "postgresql": "postgresql",
            "mongodb": "mongodb",
            "redis": "redis",
            "elasticsearch": "elasticsearch",
            "graphql": "graphql",
            
            # DevOps & Tools
            "docker": "docker",
            "kubernetes": "kubernetes",
            "git": "git",
            "github": "github",
            "gitlab": "gitlab",
            "jenkins": "jenkins",
            "circleci": "circleci",
            "travis ci": "travis",
            
            # Cloud Platforms
            "aws": "amazonwebservices",
            "google cloud": "googlecloud",
            "azure": "microsoftazure",
            "heroku": "heroku",
            "netlify": "netlify",
            "vercel": "vercel",
            "firebase": "firebase",
            
            # Testing
            "jest": "jest",
            "pytest": "pytest",
            "cypress": "cypress",
            "selenium": "selenium",
            
            # Mobile
            "react native": "react",
            "flutter": "flutter",
            "ionic": "ionic",
            
            # Other Tools
            "nginx": "nginx",
            "apache": "apache",
            "webpack": "webpack",
            "babel": "babel"
        }



    async def search_pixabay_images(self, client: httpx.AsyncClient, query: str) -> List[Dict]:
        """Search relevant business or tech imagery via Pixabay API."""
        PIXABAY_API_URL = "https://pixabay.com/api/"
        params = {
            "key": settings.PIXABAY_API_KEY,
            "q": query,
            "image_type": "photo",
            "per_page": 9,
        }
        try:
            logging.info(f"Searching Pixabay for: {query}")
            res = await client.get(PIXABAY_API_URL, params=params)
            res.raise_for_status()
            data = res.json()
            logging.info(f"Pixabay API response: {data}")
            hits = data.get("hits", [])
            return [{"url": h["webformatURL"], "tags": h.get("tags", "")} for h in hits]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logging.error(f"Pixabay API returned 400 Bad Request. This is likely due to an invalid search query. Query: '{query}', Response: {e.response.text}")
            else:
                logging.warning(f"Pixabay image search failed: {e}")
            return []
        except Exception as e:
            logging.warning(f"An unexpected error occurred during Pixabay search: {e}")
            return []

    async def search_pexels_images(self, client: httpx.AsyncClient, query: str) -> List[Dict]:
        """Search relevant business or tech imagery via Pexels API."""
        PEXELS_API_URL = "https://api.pexels.com/v1/search"
        headers = {
            "Authorization": settings.PEXELS_API_KEY
        }
        params = {
            "query": query,
            "per_page": 9,
        }
        try:
            logging.info(f"Searching Pexels for: {query}")
            res = await client.get(PEXELS_API_URL, headers=headers, params=params)
            res.raise_for_status()
            data = res.json()
            logging.info(f"Pexels API response: {data}")
            photos = data.get("photos", [])
            return [{"url": p["src"]["original"], "tags": p.get("alt", "")} for p in photos]
        except Exception as e:
            logging.warning(f"Pexels image search failed: {e}")
            return []

    async def search_images(self, query: str, provider: str = "both") -> List[Dict]:
        """Search for images from multiple providers and return the best results."""
        async with httpx.AsyncClient() as client:
            tasks = []
            if provider == "pexels" or provider == "both":
                tasks.append(self.search_pexels_images(client, query))
            if provider == "pixabay" or provider == "both":
                tasks.append(self.search_pixabay_images(client, query))

            if not tasks:
                logging.warning(f"Invalid image provider: {provider}")
                return [{"url": f"https://via.placeholder.com/800x400.png?text=Invalid+Provider", "tags": "placeholder"}]

            results = await asyncio.gather(*tasks)
            all_images = [image for result in results for image in result]
            
            if not all_images:
                logging.warning("No images found from any provider. Using placeholder.")
                return [{"url": f"https://via.placeholder.com/800x400.png?text={query}", "tags": "placeholder"}]

            return all_images

    async def get_devicon_variants(self, tech_slug: str) -> List[str]:
        """Get available devicon variants for a technology."""
        # Standard devicon variants in order of preference
        variants = [
            "original",            # Colored original logo
            "plain",              # Monochrome version
            "original-wordmark",   # Original logo with text
            "plain-wordmark",      # Monochrome logo with text
            "line",               # Line art version
            "line-wordmark",      # Line art with text
            "plain-line",         # Simple line version
            "original-line"       # Original colors with line art
        ]
        
        async with httpx.AsyncClient() as client:
            valid_variants = []
            for variant in variants:
                # Using the exact devicon CDN URL structure
                url = f"https://cdn.jsdelivr.net/gh/devicons/devicon/icons/{tech_slug}/{tech_slug}-{variant}.svg"
                try:
                    response = await client.head(url)
                    if response.status_code == 200:
                        valid_variants.append(f"{tech_slug}-{variant}")
                        break  # Stop after finding first valid variant
                except:
                    continue
            
            # If no variants found, try the base icon
            if not valid_variants:
                try:
                    url = f"https://cdn.jsdelivr.net/gh/devicons/devicon/icons/{tech_slug}/{tech_slug}.svg"
                    response = await client.head(url)
                    if response.status_code == 200:
                        valid_variants.append(tech_slug)
                except:
                    pass
            
            return valid_variants

    async def search_tech_logos(self, db: AsyncSession, query: str) -> List[Dict]:
        """Search for tech logos from both devicon and custom DB."""
        if not query:
            return []

        logging.info(f"Starting tech logo search for query: '{query}'")
        tech_logos = []

        try:
            # 1. Search in tech_name_map for devicon matches
            lower_query = query.lower()
            matched_techs = [(name, slug) for name, slug in self.tech_name_map.items() 
                           if lower_query in name.lower()]

            # 2. Get devicon variants for each matched technology
            for tech_name, tech_slug in matched_techs:
                variants = await self.get_devicon_variants(tech_slug)
                if variants:
                    # Use the first available variant
                    variant = variants[0]
                    # Construct URL using exact devicon CDN format
                    logo_url = f"https://cdn.jsdelivr.net/gh/devicons/devicon/icons/{tech_slug}/{variant}.svg"
                    tech_logos.append({
                        "name": tech_name,
                        "logo_url": logo_url,
                        "source": "devicon",
                        "variant": variant.replace(f"{tech_slug}-", "") if "-" in variant else "base"
                    })

            # 3. Search in custom logos database
            # custom_logos = await crud.get_custom_logos(db)
            # for logo in custom_logos:
            #     if lower_query in logo.name.lower():
            #         tech_logos.append({
            #             "name": logo.name,
            #             "logo_url": logo.logo_url,
            #             "source": "custom"
            #         })

            logging.info(f"Found {len(tech_logos)} tech logos in total")
            return tech_logos

        except Exception as e:
            logging.error(f"Error in unified tech logo search for '{query}': {e}")
            return []



    async def analyze_tech_stack(self, rfp: str, proposal_content: str, db: AsyncSession) -> List[Dict]:
        """Analyze the RFP and proposal content to identify the technology stack."""
        prompt = f"""As a senior solution architect, your task is to analyze the provided RFP and proposal content to identify the key technologies that form the proposed solution.

        **Context:**
        - **RFP:** ```{rfp}```
        - **Proposal Content:** ```{proposal_content}```

        **Instructions:**
        1.  **Identify Core Technologies:** From the documents, extract only the specific technologies (languages, frameworks, databases, platforms, tools) that are actively part of the proposed technical solution.
        2.  **Exclude Mentions:** Do NOT include technologies that are merely mentioned or part of the client's existing infrastructure unless they are being integrated with.
        3.  **Provide Descriptions:** For each technology, write a concise, one-sentence description of its role in the project.
        4.  **Output Format:** Return a valid JSON array of objects inside a ```json ... ``` block. Each object must have two keys: "name" (string) and "description" (string).

        **Example:**
        ```json
        [
          {{
            "name": "React",
            "description": "The primary frontend framework for building a responsive and interactive user interface."
          }},
          {{
            "name": "FastAPI",
            "description": "The backend framework for creating high-performance, asynchronous APIs to power the application."
          }},
          {{
            "name": "PostgreSQL",
            "description": "The relational database used for storing all application data securely and efficiently."
          }}
        ]
        ```

        Return ONLY the JSON array.
        """
        response_text = self.generate_response(
            message_history=[{"role": "user", "content": prompt}]
        )
        logging.info(f"Tech stack analysis response: {response_text}")
        
        try:
            tech_data = json.loads(repair_json(response_text))
            logging.info(f"Parsed tech data: {tech_data}")
        except json.JSONDecodeError as e:
            logging.error(f"LLM tech extraction failed or returned invalid result: {e}")
            tech_data = []

        logos = []
        if isinstance(tech_data, dict):
            for name, description in tech_data.items():
                if name:
                    tech_logos = await self.search_tech_logos(db, name)
                    if tech_logos:
                        for tech_logo in tech_logos:
                            logos.append({
                                "name": tech_logo["name"],
                                "logo_url": tech_logo["logo_url"],
                                "description": description,
                                "source": tech_logo.get("source", "unknown")
                            })
        elif isinstance(tech_data, list):
            for item in tech_data:
                if isinstance(item, dict) and "name" in item and "description" in item:
                    name = item["name"]
                    description = item["description"]
                    tech_logos = await self.search_tech_logos(db, name)
                    if tech_logos:
                        for tech_logo in tech_logos:
                            logos.append({
                                "name": tech_logo["name"],
                                "logo_url": tech_logo["logo_url"],
                                "description": description,
                                "source": tech_logo.get("source", "unknown")
                            })

        logging.info(f"Found {len(logos)} technology logos with descriptions")
        return logos

    async def generate_section(self, section_title: str, rfp_text: str, full_proposal_content: str, db: AsyncSession) -> dict:
        """Generates content, images, and tech logos for a single section."""
        # 1. Generate content
        # Base prompt for generating section content
        content_prompt = f"""As an expert proposal writer, generate a compelling and professional section for a business proposal titled '{section_title}'.
        The content should be based on the following RFP: {rfp_text}

        **Instructions:**
        - The tone should be professional, confident, and persuasive.
        - The content must be well-written, complete, and between 150 and 250 words.
        - Do not include the section title in your response.
        - Do not use any Markdown formatting (e.g., no `**` or `##`).
        - The output should be a single block of text, not a JSON object.

        **Example of a well-written section:**
        'Our proposed solution is a state-of-the-art platform designed to address the specific challenges outlined in the RFP. By leveraging advanced AI and machine learning algorithms, we will deliver a robust and scalable solution that will streamline your workflow and drive significant efficiency gains. Our team of experienced engineers will work closely with you to ensure a seamless implementation and a successful outcome.'

        """
        if "payment milestone" in section_title.lower():
            content_prompt = f"""As an expert proposal writer, generate a detailed HTML table for a section titled '{section_title}'.

            **Based on this RFP:** {rfp_text}

            **Instructions:**
            1.  **Output:** Generate ONLY the HTML `<table>` element. Do not include `<html>` or `<body>` tags.
            2.  **Structure:** The table should be well-structured and professional.
            3.  **Columns:** Use these columns: 'Milestone', 'Description', 'Amount'.
            4.  **Content:** Populate the table with realistic and relevant data based on the RFP.
            """
        elif "cost" in section_title.lower() or "pricing" in section_title.lower():
            content_prompt = f"""As an expert proposal writer, generate a detailed HTML table for a section titled '{section_title}'.

            **Based on this RFP:** {rfp_text}

            **Instructions:**
            1.  **Output:** Generate ONLY the HTML `<table>` element. Do not include `<html>` or `<body>` tags.
            2.  **Structure:** The table should be well-structured and professional.
            3.  **Columns:** Use these columns: 'Item', 'Description', 'Cost'.
            4.  **Content:** Populate the table with realistic and relevant data based on the RFP.
            """

        content_html = ""
        for i in range(3): # Retry up to 3 times
            message_history = [{"role": "user", "content": content_prompt}]
            response = self.generate_response(message_history)
            
            if response and len(response) > 100:
                content_html = response
                break
            else:
                logging.warning(f"Content validation failed on attempt {i+1} for section '{section_title}'. Retrying...")
        
        if not content_html:
            logging.error(f"Failed to generate valid content for section '{section_title}' after multiple retries.")
            content_html = "Error generating content."

        # 2. Analyze for tech logos if it's the Technology Stack section
        tech_logos = []
        if "technology stack" in section_title.lower():
            tech_logos = await self.analyze_tech_stack(rfp_text, full_proposal_content, db)

        # 3. Search for images for other sections
        image_urls = []
        if "technology stack" not in section_title.lower() and "about us" not in section_title.lower() and "company" not in section_title.lower() and "logo" not in section_title.lower() and "payment milestone" not in section_title.lower():
            try:
                rfp_keywords = self.get_image_query_from_text(rfp_text)
                content_keywords = self.get_image_query_from_text(content_html)
                image_query = f"{section_title} {rfp_keywords} {content_keywords}".strip()
                image_query = image_query[:100]
                logging.info(f"Searching for image with query: {image_query}")
                images = await self.search_images(image_query)
                if images:
                    image_urls = [images[0]["url"]]
            except Exception as e:
                logging.error(f"Error searching for image for section {section_title}: {e}")

        return {
            "contentHtml": content_html,
            "image_urls": image_urls,
            "tech_logos": tech_logos
        }

    async def enhance_section(self, section: Dict, instructions: str, tone: str, focus_points: Optional[List[str]] = None) -> Dict:
        """Enhances an existing section's content based on provided instructions.

        This method accepts either a dict-like or pydantic Section object.
        """
        # Normalize inputs (work with dict or object)
        if isinstance(section, dict):
            title = section.get("title")
            content = section.get("contentHtml") or section.get("content") or ""
        else:
            title = getattr(section, "title", None)
            content = getattr(section, "contentHtml", None) or getattr(section, "content", "")

        logging.info(f"Enhancing section '{title}' with instructions: {instructions}")

        focus_text = ", ".join(focus_points) if focus_points else "None specified."

        # Construct the prompt for enhancement
        prompt = f"""
        You are an expert proposal writer. Your task is to enhance and refine the provided section of a business proposal.

        **Current Section Title:** {title or 'Untitled'}
        **Current Section Content:**
        ```
        {content}
        ```

        **Enhancement Instructions:** {instructions}
        **Desired Tone:** {tone}
        **Key Focus Points:** {focus_text}

        **Guidelines for Enhancement:**
        - Improve clarity, conciseness, and persuasiveness.
        - Ensure the content aligns with the specified tone.
        - Incorporate the key focus points naturally and effectively.
        - Correct any grammatical errors or awkward phrasing.
        - Maintain the core message and factual accuracy of the original content.
        - The enhanced content should be well-written, complete, and between 150 and 300 words.
        - Do not include the section title in your response.
        - Do not use any Markdown formatting (e.g., no `**` or `##`).
        - The output should be a single block of text, not a JSON object.

        Return ONLY the enhanced content.
        """

        enhanced_content_html = ""
        for i in range(3):  # Retry up to 3 times
            message_history = [{"role": "user", "content": prompt}]
            response = self.generate_response(message_history)

            if response and len(response) > 100:  # Basic validation for response length
                enhanced_content_html = response
                break
            else:
                logging.warning(f"Content enhancement validation failed on attempt {i+1} for section '{title}'. Retrying...")

        if not enhanced_content_html:
            logging.error(f"Failed to generate valid enhanced content for section '{title}' after multiple retries.")
            enhanced_content_html = content or "Error enhancing content."

        # For now, we only return the content. Image and tech logo generation can be added later if needed for enhancement.
        return {
            "content": enhanced_content_html,
            "title": title  # Keep original title for now
        }

content_writer_agent = ContentWriterAgent(client=client)
