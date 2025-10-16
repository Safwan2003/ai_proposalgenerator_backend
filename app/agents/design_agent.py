import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
from groq import Groq
from dotenv import load_dotenv
from app.schemas import Proposal  # keep your existing proposal schema

# ---------------------------------------------------------------------
# Environment setup
# ---------------------------------------------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEFAULT_MODEL = os.getenv("GROQ_MODEL_NAME", "meta-llama/llama-4-scout-17b-16e-instruct")

if not GROQ_API_KEY:
    logging.warning("⚠️ GROQ_API_KEY not found in environment; Groq client may fail.")

client = Groq(api_key=GROQ_API_KEY)


# ---------------------------------------------------------------------
# Design Agent
# ---------------------------------------------------------------------
class DesignAgent:
    """
    AI-powered design system generator for premium proposal layouts.
    Includes collaborative design generation, theme evolution,
    and multi-variant design suggestion support.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or DEFAULT_MODEL

    # -----------------------------------------------------------------
    # JSON & CSS utility helpers
    # -----------------------------------------------------------------
    @staticmethod
    def _extract_json_array(text: str) -> Optional[str]:
        """Try to find and return the first valid JSON array in the text."""
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if match:
            return match.group(0)
        objs = re.findall(r"\{(?:[^\{\}]|\n)*?\}", text, re.DOTALL)
        if objs:
            return "[" + ",".join(objs) + "]"
        return None

    @staticmethod
    def _clean_css(css_text: str) -> str:
        """Remove markdown fences, normalize whitespace, and strip comments."""
        if not css_text:
            return ""
        css_text = re.sub(r"^```(?:css)?\s*", "", css_text.strip(), flags=re.IGNORECASE)
        css_text = re.sub(r"\s*```$", "", css_text.strip(), flags=re.IGNORECASE)
        css_text = re.sub(r"/\*[\s\S]*?\*/", "", css_text)
        return css_text.replace("\r\n", "\n").strip()

    @staticmethod
    def _validate_hex(hex_color: str) -> bool:
        return bool(re.match(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", (hex_color or "").strip()))

    @staticmethod
    def _safe_json_load(text: str) -> Any:
        """Attempt robust JSON parsing with regex fallback."""
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            candidate = DesignAgent._extract_json_array(text)
            if candidate:
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    sanitized = re.sub(r",\s*([}\]])", r"\1", candidate)
                    try:
                        return json.loads(sanitized)
                    except Exception:
                        return None
        return None

    # -----------------------------------------------------------------
    # Core design generation
    # -----------------------------------------------------------------
    def _generate_base_theme(self, proposal: Proposal, all_visual_tones: List[str]) -> str:
        """Generates the foundational CSS theme via Groq LLM (fallback to default)."""
        prompt = f"""
        You are a world-class UI/UX design director, inspired by StoryDoc and Apple-style minimalism.
        Generate a production-ready, light-mode only CSS theme for a business proposal.

        Requirements:
        - Container: .proposal-container, max-width: 1000px, centered.
        - Headings: full-width colored background strips (extend to viewport).
        - Typography: 'Inter' for body, 'Poppins' for headings.
        - Aesthetic: Clean, professional, modern, bright.
        - Color palette: Declare CSS variables in :root for primary, secondary, accent, surface, background, text, muted.
        - Shadows and border-radius for sections.
        - NO dark backgrounds, NO dark mode.
        - Output CSS only (no explanations, no markdown fences).

        Context:
        Client: {proposal.clientName}
        Company: {proposal.companyName}
        Visual Tones: {', '.join(all_visual_tones)}
        """
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._clean_css(resp.choices[0].message.content)
        except Exception as exc:
            logging.exception("Error in _generate_base_theme: %s", exc)
            return self.get_default_design()[0]["css"]

    def _generate_layout_css(self, layout_type: str, visual_tone: str) -> str:
        """Generates layout-specific CSS via LLM (fallback message on error)."""
        prompt = f"""
        Design CSS for a layout section named `.{layout_type}`.
        It should look {visual_tone}, professional, and complement a white proposal background.
        Use Flexbox or CSS Grid if relevant.
        Output pure CSS only.
        """
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._clean_css(resp.choices[0].message.content)
        except Exception as exc:
            logging.exception("Error in _generate_layout_css for %s: %s", layout_type, exc)
            return f"/* Failed to generate layout {layout_type} */"

    def generate_collaborative_design(self, proposal: Proposal) -> str:
        """Generate a context-aware design with base theme and layout CSS."""
        if not proposal or not getattr(proposal, "sections", None):
            return "/* Proposal missing content */"

        unique_layouts, all_visual_tones = {}, []
        for section in proposal.sections:
            hints = section.get("design_hints", {}) if isinstance(section, dict) else getattr(section, "design_hints", {})
            layout = hints.get("layout_type", "standard-text")
            tone = hints.get("visual_tone", "professional")
            unique_layouts.setdefault(layout, tone)
            all_visual_tones.append(tone)

        base_css = self._generate_base_theme(proposal, list(set(all_visual_tones)))
        layout_css = [self._generate_layout_css(l, t) for l, t in unique_layouts.items() if l != "standard-text"]

        return "\n\n".join([base_css] + layout_css)

    # -----------------------------------------------------------------
    # Default design fallback (single, cleaned CSS block)
    # -----------------------------------------------------------------
    def get_default_design(self) -> List[Dict[str, str]]:
        """Default premium light theme with full-width header strips and centered content."""
        css = """
:root {
  --primary: #1e3a8a;
  --secondary: #2563eb;
  --accent: #06b6d4;
  --background: #f9fafb;
  --surface: #ffffff;
  --text: #1f2937;
  --muted: #6b7280;
  --radius: 16px;
  --shadow: 0 8px 24px rgba(0,0,0,0.08);
  --heading-font: 'Poppins', sans-serif;
  --body-font: 'Inter', sans-serif;
}

/* Page */
html, body {
  margin: 0;
  padding: 0;
  background: var(--background);
  color: var(--text);
  font-family: var(--body-font);
  color-scheme: light;
}

/* Centered container: all content constrained to 1000px and centered */
.proposal-container {
  max-width: 1000px;
  margin: 0 auto;
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 3rem 2rem;
  position: relative;
  z-index: 2;
}

/* Section card */
.proposal-section {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 3rem 2rem;
  margin: 2.5rem auto;
  box-shadow: var(--shadow);
  border-top: 8px solid var(--accent);
  transition: transform 0.2s ease, box-shadow 0.3s ease;
  max-width: 1000px;
}
.proposal-section:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
}

/* Recommended: wrap headings with .section-header for best alignment:
   <div class="section-header"><h1>Title</h1></div>
   Fallback below applies when headings are used directly. */

/* Full-width header strip wrapper */
.section-header {
  position: relative;
  background: linear-gradient(90deg, var(--primary), var(--secondary));
  color: #fff;
  text-align: center;
  padding: 1.2rem 0;
  font-family: var(--heading-font);
  font-weight: 600;
  font-size: 2.4rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  z-index: 1;
}
.section-header h1, .section-header h2, .section-header h3 {
  margin: 0;
  color: #fff;
}

/* Fallback: direct h1/h2/h3 as full-width strips */
h1, h2, h3 {
  font-family: var(--heading-font);
  color: #ffffff;
  background: linear-gradient(90deg, var(--primary), var(--secondary));
  text-align: center;
  padding: 1rem 0;
  margin: 3rem 0 1.5rem;
  font-weight: 600;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}
h1 { font-size: 2.8rem; }
h2 { font-size: 2.2rem; }
h3 { font-size: 1.6rem; }

/* Images centered and responsive */
.proposal-section img {
  display: block;
  max-width: 90%;
  height: auto;
  margin: 2rem auto;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

/* Tech logos grid */
.tech-stack-logos {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 2rem;
  padding: 1rem;
  margin-top: 2rem;
  background: linear-gradient(90deg, rgba(37,99,235,0.04), rgba(6,182,212,0.04));
  border-radius: 12px;
}
.tech-stack-logos img {
  width: 72px;
  height: 72px;
  object-fit: contain;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  border-radius: 8px;
}
.tech-stack-logos img:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
}

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: var(--shadow);
}
th, td {
  padding: 0.9rem 1rem;
  text-align: left;
  border-bottom: 1px solid rgba(2,6,23,0.05);
}
th {
  background: var(--secondary);
  color: #fff;
  text-transform: uppercase;
  font-size: 0.85rem;
}

/* Diagrams container */
.diagram-container {
  display: flex;
  justify-content: center;
  margin: 2rem 0;
}
.diagram-container .mermaid {
  max-width: 90%;
  background: #f8fafc;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.05);
}

/* Footer */
footer {
  text-align: center;
  font-size: 0.9rem;
  color: var(--muted);
  padding-top: 2rem;
  border-top: 1px solid rgba(2,6,23,0.05);
  margin-top: 3rem;
}
"""
        return [{"prompt": "Premium Full-Width Proposal", "css": css}]

    # -----------------------------------------------------------------
    # CSS evolution & customization (unchanged behavior)
    # -----------------------------------------------------------------
    def customize_design(self, css: str, customization_request: str) -> str:
        """Modify CSS per user's design customization request."""
        prompt = f"""
You are an expert CSS designer.
Modify the CSS below according to this request: "{customization_request}"
Rules:
- Keep all existing class names.
- Focus on subtle gradients, accessibility, typography refinement.
- Keep structure and spacing intact.
Output ONLY the final CSS.
CSS:
{css}
"""
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=0.85,
                top_p=0.95,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._clean_css(resp.choices[0].message.content)
        except Exception as exc:
            logging.exception("Error in customize_design: %s", exc)
            return css

    def evolve_design(self, css: str, target_style: str) -> str:
        """Evolve a CSS theme toward a target style (Luxury, Futuristic, etc.)."""
        prompt = f"""
Refine this CSS to make it feel '{target_style}'.
Keep class names, spacing, and structure intact.
Enhance color palette, typography, shadows, and transitions.
Return only the CSS (no explanations).
CSS:
{css}
"""
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=0.95,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._clean_css(resp.choices[0].message.content)
        except Exception as exc:
            logging.exception("Error in evolve_design: %s", exc)
            return css

    # -----------------------------------------------------------------
    # Multi-theme suggestions & component CSS (unchanged)
    # -----------------------------------------------------------------
    def get_design_suggestions(self, proposal: Proposal, keywords: str = "") -> List[Dict[str, Any]]:
        if not proposal or not getattr(proposal, "sections", None):
            raise ValueError("Proposal content missing.")

        system_message = {
            "role": "system",
            "content": (
                "You are a UI/UX design director. Output JSON array with objects containing: "
                "'prompt', 'metadata', and 'css'. Metadata must include primary_color, secondary_color, font, tone, "
                "layout_style, header_style, section_style, and visual_description."
            ),
        }

        prompt = f"""
Generate 3 to 4 unique CSS design themes for this proposal.
Each entry: {{ "prompt": "", "metadata": {{"primary_color":"","secondary_color":"","font":"","tone":"", "layout_style":"", "header_style":"", "section_style":"", "visual_description":""}}, "css": "" }}
For each design, provide a brief visual description in the 'visual_description' field.
Use light backgrounds, accessible contrast, and distinct tones.
Client: {proposal.clientName}
Company: {proposal.companyName}
Analyze the following RFP text to understand the client's brand, industry, and desired tone. Incorporate these insights into the design themes, focusing on professionalism, readability, and brand consistency.
RFP: {proposal.rfpText[:600]}
Keywords: {keywords}
Output JSON array only.
"""
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=1.0,
                messages=[system_message, {"role": "user", "content": prompt}],
            )
            parsed = self._safe_json_load(resp.choices[0].message.content)
            designs = []
            if parsed:
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    meta = item.get("metadata", {})
                    css = self._clean_css(item.get("css", ""))
                    designs.append({
                        "prompt": item.get("prompt", meta.get("tone", "Variant")),
                        "metadata": meta,
                        "css": css,
                    })
            
            # Ensure a minimum of 3 designs
            default_designs = self.get_default_design()
            while len(designs) < 3:
                if default_designs:
                    designs.append(default_designs[0])
                else:
                    break

            return designs
        except Exception as exc:
            logging.exception("Error in get_design_suggestions: %s", exc)
            return self.get_default_design()

    def generate_component_css(self, component_description: str) -> str:
        prompt = f"""
Create CSS only for this UI component:
"{component_description}"
Keep light theme, modern style, and accessibility.
Output CSS only.
"""
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._clean_css(resp.choices[0].message.content)
        except Exception as exc:
            logging.exception("Error in generate_component_css: %s", exc)
            return ""


# ---------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------
design_agent = DesignAgent()
