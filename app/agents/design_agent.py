import os
import re
import json
from typing import List
from dotenv import load_dotenv
from groq import Groq
from .. import schemas

# Load environment variables
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


class DesignAgent:
    """
    AI-powered agent that generates design suggestions and premium CSS for proposals.
    """

    def _fix_json_string(self, s: str) -> str:
        """
        Corrects a JSON string where CSS content is incorrectly wrapped in backticks (` `)
        instead of proper JSON string literals.
        """
        pattern = re.compile(r'("css":\s*)`([^"]*)`', re.DOTALL)

        def replacer(match):
            # Group 1 is the key ("css": )
            # Group 2 is the CSS content
            # json.dumps correctly escapes the content and wraps it in double quotes.
            return match.group(1) + json.dumps(match.group(2))

        return pattern.sub(replacer, s)

    def get_design_suggestions(self, proposal: schemas.Proposal) -> List[dict]:
        if not client.api_key:
            print("GROQ_API_KEY is not set. Returning default suggestions.")
            return self._default_suggestions_with_css()

        content_summary = f"Client: {proposal.clientName}\
"
        content_summary += f"RFP Summary: {proposal.rfpText[:500]}...\n"
        for section in proposal.sections:
            content_summary += f"Section: {section.title}\
"

        system_prompt = f"""
        You are an elite-level digital designer and CSS architect. Your task is to generate a portfolio of 4 distinct, production-quality design themes for a business proposal. The design should be thematically aligned with the proposal's content.

        **Proposal Content Summary:**
        {content_summary}

        **Instructions:**
        Generate a JSON array of 4 design objects. Each object must have a 'prompt' (the theme name) and 'css' (the stylesheet).
        The 4 themes MUST be based on the following specific aesthetics, but adapted to the proposal's content:
        1.  **Corporate & Clean**: A minimalist, professional light theme. Bright, airy, with a single, strong accent color. Use a sans-serif font like 'Lato' or 'Open Sans'. The design should feel trustworthy and reliable.
        2.  **Bold & Modern (Dark Theme)**: A striking dark theme. High contrast, with vibrant text and accent colors on a dark background. Use a modern, geometric sans-serif font like 'Poppins'. This design should feel innovative and forward-thinking.
        3.  **Elegant & Classic**: A refined, traditional design. Use a serif font like 'Merriweather' or 'Lora' for body text. The layout should be formal and balanced, conveying a sense of prestige and quality.
        4.  **Creative & Asymmetrical**: An "out-of-the-box" design. Experiment with an asymmetrical layout, perhaps using CSS Grid or Flexbox in a more creative way to position section titles and content. This design should feel dynamic and original.

        **Universal CSS Requirements for ALL themes:**
        - **Google Fonts**: Import the chosen fonts at the top of the CSS using `@import`.
        - **CSS Variables**: Define and use CSS variables for a harmonious color palette (`--primary-color`, `--secondary-color`, `--accent-color`, `--bg-color`, `--text-color`) and fonts (`--font-primary`, `--font-secondary`).
        - **Advanced Layout**: Use modern layout techniques like CSS Grid or Flexbox to create a well-structured and responsive design. For the 'Creative & Asymmetrical' theme, be particularly innovative with the layout.
        - **Responsive Design**: All themes must be fully responsive and look great on mobile, tablet, and desktop.
        - **Complete Styling**: Provide comprehensive styling for all elements: `h1`, `h2`, `h3`, `p`, `blockquote`, `table`, `th`, `td`, `ul`, `ol`, `li`, and `a`.
        - **Interactive Polish**: Add subtle hover effects for links and buttons, and consider using smooth transitions for a more dynamic feel.
        - **Container**: All styles must be scoped to the `.proposal-container` and its children to avoid affecting the rest of the UI.
        - **Image Styling**: Images should be styled with `max-width: 100%; height: auto; border-radius: 8px;` and a subtle `box-shadow`.

        Return ONLY the raw JSON array. Do not include any markdown formatting or explanatory text.
        """

        try:
            print("Fetching design suggestions with CSS from Groq API...")
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the 4 design suggestions now."},
                ],
                model="llama-3.3-70b-versatile", # Using a more powerful model for this complex task
                temperature=0.7,
            )

            response_content = chat_completion.choices[0].message.content.strip()
            print(f"Groq raw response: {response_content}")

            # More robustly find the JSON block
            start_index = response_content.find('[')
            end_index = response_content.rfind(']')

            if start_index != -1 and end_index != -1 and end_index > start_index:
                json_string = response_content[start_index:end_index + 1]
                try:
                    # First, fix the non-standard backticks from the AI response
                    repaired_json_string = self._fix_json_string(json_string)
                    
                    parsed_json = json.loads(repaired_json_string)
                    if isinstance(parsed_json, list) and all(isinstance(item, dict) and 'prompt' in item and 'css' in item for item in parsed_json):
                        return parsed_json
                except json.JSONDecodeError as e:
                    print(f"Failed to decode JSON from AI response: {e}")
                    print(f"Malformed JSON string after repair attempt: {repaired_json_string}")

            print("Could not find or parse valid JSON in AI response. Returning default suggestions.")
            return self._default_suggestions_with_css()

        except Exception as e:
            print(f"Error generating design suggestions: {e}")
            import traceback
            traceback.print_exc()
            return self._default_suggestions_with_css()

    def _default_suggestions_with_css(self) -> List[dict]:
        return [
            {
                "prompt": "Corporate & Clean",
                "css": self._default_corporate_clean_css()
            },
            {
                "prompt": "Bold & Modern (Dark Theme)",
                "css": self._default_bold_modern_css()
            },
            {
                "prompt": "Elegant & Classic",
                "css": self._default_elegant_classic_css()
            },
            {
                "prompt": "Creative & Asymmetrical",
                "css": self._default_creative_asymmetrical_css()
            }
        ]

    def _default_corporate_clean_css(self) -> str:
        return """
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');
        .proposal-container {
            --primary-color: #0052cc;
            --text-color: #333;
            --bg-color: #ffffff;
            --font-primary: 'Open Sans', sans-serif;
            font-family: var(--font-primary);
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 2rem;
        }
        .proposal-container h1, .proposal-container h2, .proposal-container h3 {
            color: var(--primary-color);
            font-weight: 700;
        }
        """

    def _default_bold_modern_css(self) -> str:
        return """
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
        .proposal-container {
            --primary-color: #6f42c1;
            --text-color: #f8f9fa;
            --bg-color: #1a1a1a;
            --font-primary: 'Poppins', sans-serif;
            font-family: var(--font-primary);
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 2rem;
        }
        .proposal-container h1, .proposal-container h2, .proposal-container h3 {
            color: var(--primary-color);
            font-weight: 700;
        }
        """

    def _default_elegant_classic_css(self) -> str:
        return """
        @import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;600&family=Merriweather:wght@400;700&display=swap');
        .proposal-container {
            --primary-color: #8B4513;
            --text-color: #333;
            --bg-color: #fdfdfd;
            --font-primary: 'Merriweather', serif;
            --font-secondary: 'Lora', serif;
            font-family: var(--font-secondary);
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 2rem;
        }
        .proposal-container h1, .proposal-container h2, .proposal-container h3 {
            font-family: var(--font-primary);
            color: var(--primary-color);
            font-weight: 700;
        }
        """

    def _default_creative_asymmetrical_css(self) -> str:
        return """
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');
        .proposal-container {
            --primary-color: #d9534f;
            --text-color: #333;
            --bg-color: #fff;
            --font-primary: 'Montserrat', sans-serif;
            font-family: var(--font-primary);
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 2rem;
        }
        .proposal-container .proposal-section {
            display: grid;
            grid-template-columns: 1fr 3fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }
        .proposal-container .proposal-section h2 {
            text-align: right;
            padding-right: 1rem;
            border-right: 3px solid var(--primary-color);
        }
        """

    def generate_css(self, proposal: schemas.Proposal, prompt: str) -> str:
        if not client.api_key:
            print("GROQ_API_KEY is not set. Returning default CSS.")
            return self._default_corporate_clean_css()
        """
        Generate premium custom CSS for a proposal based on its content and a user prompt.
        """

        content_summary = (
            f"Client: {proposal.clientName}\n"
            f"RFP Summary: {proposal.rfpText[:500]}...\n"
            f"Company: {proposal.companyName}"
        )

        system_prompt = """
        You are an elite AI design architect. Your task is to generate production-quality,
        premium CSS for a business proposal web layout. The proposal is always wrapped
        inside `.proposal-container`.

        ### Core Design Principles
        - **Typography Excellence**: Use modern, refined typography.
        Pair a strong sans-serif for headings with an elegant serif for body text.
        Use fluid font sizing with `clamp()` for perfect scaling across devices.
        - **Color Systems**: Define a harmonious palette with CSS variables:
        `--primary-color`, `--secondary-color`, `--accent-color`, `--bg-color`, `--text-color`.
        Ensure accessible contrast and visual hierarchy.
        - **Spacing & Layout**: Provide generous whitespace for readability.
        Use Flexbox and CSS Grid for adaptive, responsive layouts.
        The `.proposal-container` should look balanced on mobile, tablet, and desktop.
        - **Interactive Polish**: Add subtle hover, focus, and active states.
        Use smooth transitions and transforms (`scale`, `translateY`, `rotate`) to create micro-interactions.
        - **UI Components**: Style not just text, but also proposal UI elements:
        - `.section` blocks as elevated cards with shadows and rounded corners.
        - `.btn` buttons with hover/active effects and accessible contrast.
        - `.callout` or `blockquote` areas with accent borders and backgrounds.
        - Tables (`table, th, td`) with clean, professional styling.
        - **Modern Finishes**: Use border-radius, layered shadows, and gradients subtly.
        All images (`img`) should be responsive (`max-width: 100%; height: auto;`) with rounded corners.

        ### Output Rules
        - Scope **all styles** to `.proposal-container` and its children (avoid leaking global styles).
        - Define CSS variables at the top and reuse them consistently.
        - Ensure responsiveness and accessibility best practices.
        - Return ONLY raw CSS. No markdown, no explanations.
        """


        user_prompt = f"""
        Proposal Context:
        {content_summary}

        User Design Prompt: "{prompt}"
        """

        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.9,
            )
            return chat_completion.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating CSS: {e}")
            return self._default_corporate_clean_css()

design_agent = DesignAgent()