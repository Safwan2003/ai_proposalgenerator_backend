import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
from groq import Groq
from dotenv import load_dotenv
from app.schemas import Proposal
from json_repair import repair_json

# Environment and API setup
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEFAULT_MODEL = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'design_templates')

if not GROQ_API_KEY:
    logging.warning("GROQ_API_KEY not found; Groq client may fail.")

client = Groq(api_key=GROQ_API_KEY)

class DesignAgent:
    """
    Generates proposal designs by creating AI-powered design tokens and injecting them into a CSS template.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or DEFAULT_MODEL
        self.template = self._load_template()

    def _load_template(self) -> str:
        """Load the single master CSS template."""
        template_path = os.path.join(TEMPLATE_DIR, 'document.css')
        if not os.path.exists(template_path):
            logging.error(f"Master template 'document.css' not found at {template_path}")
            return "/* Master template not found. */"
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logging.error(f"Error loading master template: {e}")
            return "/* Error loading template. */"

    def _generate_design_tokens(self, proposal: Proposal, theme_prompt: str) -> Dict[str, Any]:
        """Uses AI to generate a JSON object of design tokens based on a theme prompt."""
        system_message = {
            "role": "system",
            "content": (
                "You are a world-class UI/UX design director. Your task is to generate a JSON object of design tokens "
                "for a business proposal. The output must be only the JSON object, with no other text."
            )
        }
        
        prompt = f"""
        Generate a JSON object of design tokens for a business proposal with the theme: '{theme_prompt}'.

        The proposal is for client '{proposal.clientName}' from company '{proposal.companyName}'.
        RFP context: {proposal.rfpText[:500]}

        The JSON object must include the following keys and value types:
        - "prompt": string (a short, catchy name for this theme)
        - "colors": {{ "primary": hex, "secondary": hex, "accent": hex, "background": hex, "surface": hex, "muted": hex, "border": hex, "text-primary": hex, "text-secondary": hex, "text-inverted": hex, "text-muted": hex }}
        - "fonts": {{ "heading": string (e.g., 'Poppins, sans-serif'), "body": string (e.g., 'Inter, sans-serif') }}
        - "spacing": {{ "xs": string, "sm": string, "md": string, "lg": string, "xl": string, "xxl": string }}
        - "radius": {{ "sm": string, "md": string, "lg": string }}
        - "shadows": {{ "sm": string, "md": string, "lg": string }}
        - "typography": {{ "h1": string, "h2": string, "h3": string, "lead-size": string }}
        - "layout": {{ "proposal-max-width": string }}

        Return only the JSON object.
        """

        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=0.9,
                messages=[system_message, {"role": "user", "content": prompt}],
            )
            response_text = resp.choices[0].message.content
            return json.loads(repair_json(response_text))
        except Exception as e:
            logging.error(f"Error generating design tokens for prompt '{theme_prompt}': {e}")
            return {{}}

    def _tokens_to_css_variables(self, tokens: Dict[str, Any]) -> str:
        """Converts a dictionary of design tokens into a CSS :root variable block."""
        if not tokens:
            return ""
        
        lines = [":root {"]
        for category, values in tokens.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    lines.append(f"  --{category}-{key}: {value};")
        lines.append("}")
        return "\n".join(lines)

    def generate_collaborative_design(self, proposal: Proposal) -> str:
        """Generates a complete CSS stylesheet by creating tokens and injecting them into the template."""
        # For the primary design, we can use a default professional prompt.
        theme_prompt = f"A clean, professional, and modern design suitable for a high-value corporate client like {proposal.clientName}."
        tokens = self._generate_design_tokens(proposal, theme_prompt)
        
        if not tokens:
            logging.warning("Failed to generate tokens, returning default template.")
            return self.template

        css_variables = self._tokens_to_css_variables(tokens)
        return f"{css_variables}\n\n{self.template}"

    def _get_dynamic_theme_prompts(self, proposal: Proposal) -> List[str]:
        """Analyzes the proposal and generates a list of 2-3 dynamic, context-aware theme prompts."""
        system_message = {
            "role": "system",
            "content": "You are a creative director. Based on the provided proposal context, generate a JSON array of 3 distinct, one-sentence theme prompts for a visual designer. Output only the JSON array."
        }
        
        prompt = f"""
        Analyze the following proposal context and generate 3 distinct, one-sentence theme prompts.
        Each prompt should suggest a clear creative direction for the visual design.

        Client: {proposal.clientName}
        RFP Context: {proposal.rfpText[:800]}

        Example Output:
        ```json
        [
            "A trustworthy and secure theme for a financial institution, using a stable color palette of deep blues and grays.",
            "A clean, minimalist, and modern theme for a tech startup, using a vibrant accent color to convey innovation.",
            "An elegant and professional theme for a high-end consulting firm, featuring classic fonts and a luxurious feel."
        ]
        ```
        """
        
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=0.9,
                messages=[system_message, {"role": "user", "content": prompt}],
            )
            response_text = resp.choices[0].message.content
            return json.loads(repair_json(response_text))
        except Exception as e:
            logging.error(f"Error generating dynamic theme prompts: {e}")
            # Fallback to generic prompts
            return [
                f"A trustworthy and elegant theme with a classic feel, suitable for a financial or legal client.",
                f"A bold, high-contrast, and impactful theme that makes a strong statement.",
                f"A minimalist and clean theme using a muted, professional color palette."
            ]

    def get_design_suggestions(self, proposal: Proposal, keywords: str = "") -> List[Dict[str, Any]]:
        """Generates 2-3 distinct and context-aware design themes (token sets) for the user to choose from."""
        
        # Generate dynamic prompts based on proposal content
        theme_prompts = self._get_dynamic_theme_prompts(proposal)

        designs = []
        for theme_prompt in theme_prompts:
            tokens = self._generate_design_tokens(proposal, theme_prompt)
            if tokens:
                css_variables = self._tokens_to_css_variables(tokens)
                full_css = f"{css_variables}\n\n{self.template}"
                designs.append({
                    "prompt": tokens.get("prompt", "AI Suggested Design"),
                    "css": full_css,
                    "metadata": {"tokens": tokens}
                })
        
        if not designs:
            logging.warning("Failed to generate any design suggestions, returning default.")
            # Fallback to generating a single default design
            default_tokens = self._generate_design_tokens(proposal, "A clean, professional, and modern design.")
            if default_tokens:
                css_vars = self._tokens_to_css_variables(default_tokens)
                return [{"prompt": "Default Professional Design", "css": f"{css_vars}\n\n{self.template}", "metadata": {"tokens": default_tokens}}]
            return [{"prompt": "Default Design", "css": self.template, "metadata": {}}]
            
        return designs

    def customize_design(self, css: str, customization_request: str) -> str:
        """Modifies the :root variables of a CSS file based on a user request."""
        # This is a simplified version. A robust implementation would parse the tokens,
        # ask the AI to modify the JSON, and then regenerate the CSS.
        prompt = f"""
        You are a CSS expert. Modify the :root {{...}} block of the following CSS according to the request: "{customization_request}"
        Do not change any other part of the CSS. Output the entire, modified CSS.

        CSS:
        {css}
        """
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except Exception as e:
            logging.exception("Error in customize_design: %s", exc)
            return css

# Global instance
design_agent = DesignAgent()
