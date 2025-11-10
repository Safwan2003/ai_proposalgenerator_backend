import logging
import os
import re
import time
from typing import Dict, Any
from groq import Groq, RateLimitError, APIError
from app.core.config import settings
from .base_agent import ConversableAgent

# ---------------------------------------------------------------------
# GLOBAL CONFIG
# ---------------------------------------------------------------------
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
RATE_LIMIT_BACKOFF_TIME = 15
MAX_RETRIES = 4


# ---------------------------------------------------------------------
# EXCEPTIONS
# ---------------------------------------------------------------------
class ChartValidationError(Exception):
    pass


class ChartGenerationError(Exception):
    pass


# ---------------------------------------------------------------------
# MAIN CLASS
# ---------------------------------------------------------------------
class DiagramAgent(ConversableAgent):
    """Agent for generating and validating Mermaid.js diagrams using the Groq LLM."""

    def __init__(self, client: Groq):
        super().__init__(
            name="DiagramAgent",
            system_message="You are an expert in creating Mermaid.js diagrams. Generate valid Mermaid code.",
            client=client,
        )
        self.valid_keywords = [
            "graph", "gantt", "pie", "sequence", "mindmap", "journey", "c4", "%%"
        ]
        self.model = os.environ.get("GROQ_DIAGRAM_MODEL_NAME", settings.GROQ_MODEL_DEFAULT)

    # ---------------------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------------------
    def _validate_chart_syntax(self, chart_code: str) -> Dict[str, Any]:
        """Basic static validation of Mermaid syntax structure."""
        result = {"valid": False, "errors": [], "warnings": []}
        if not chart_code or not chart_code.strip():
            result["errors"].append("Empty chart code")
            return result

        lc = chart_code.lower()
        if not any(lc.startswith(v) for v in self.valid_keywords) and not lc.startswith("%%"):
            result["errors"].append("Invalid chart start syntax")

        # basic bracket matching
        pairs = {"{": "}", "(": ")", "[": "]"}
        stack = []
        for i, line in enumerate(chart_code.splitlines(), start=1):
            for ch in line:
                if ch in pairs:
                    stack.append((ch, i))
                elif ch in pairs.values():
                    if not stack:
                        result["errors"].append(f"Unmatched closing '{ch}' at line {i}")
                    else:
                        o, ln = stack.pop()
                        if pairs[o] != ch:
                            result["errors"].append(f"Mismatched {o}/{ch} between lines {ln} and {i}")

        if stack:
            result["errors"].append("Unclosed symbols")

        result["valid"] = not result["errors"]
        return result

    # ---------------------------------------------------------------------
    # LLM CHART GENERATION
    # ---------------------------------------------------------------------
    def _generate_chart(self, prompt: str, retries: int = MAX_RETRIES) -> str:
        """Generate a diagram using Groq and extract valid Mermaid code."""
        last_error = None
        for attempt in range(retries):
            try:
                logging.info(f"DiagramAgent: generating chart (attempt {attempt + 1}/{retries})")
                response_content = self.generate_response([{"role": "user", "content": prompt}])
                if not response_content:
                    raise ChartGenerationError("Empty LLM response")

                # Extract mermaid code block
                match = re.search(r"```mermaid\s*(.*?)```", response_content, re.DOTALL)
                if not match:
                    chart_code = self._sanitize_chart_code(response_content)
                    validation = self._validate_chart_syntax(chart_code)
                    if validation["valid"]:
                        return chart_code
                    else:
                        raise ChartValidationError(
                            f"No ```mermaid``` block found and whole response is invalid. "
                            f"Validation errors: {validation['errors']}"
                        )

                chart_code = match.group(1).strip()
                chart_code = self._sanitize_chart_code(chart_code)
                validation = self._validate_chart_syntax(chart_code)

                if validation["valid"]:
                    return chart_code
                else:
                    raise ChartValidationError(
                        f"Extracted mermaid block is invalid. "
                        f"Content: {chart_code[:500]}..., Validation Result: {validation}"
                    )

            except RateLimitError as e:
                last_error = e
                logging.warning("Rate limit hit; backing off")
                time.sleep(RATE_LIMIT_BACKOFF_TIME)
                continue
            except APIError as e:
                last_error = e
                logging.warning(f"API error: {e}; retrying")
                time.sleep(2 ** attempt)
                continue
            except Exception as e:
                last_error = e
                logging.warning(f"Generation error: {e}; retrying")
                time.sleep(2 ** attempt)
                continue

        raise ChartGenerationError(f"Failed to generate chart after {retries} attempts: {last_error}")

    # ---------------------------------------------------------------------
    # SANITIZER
    # ---------------------------------------------------------------------
    def _sanitize_chart_code(self, chart_code: str) -> str:
        """Fix invalid Mermaid syntax automatically."""
        chart_code = re.sub(r"\|>+", "|", chart_code)
        chart_code = re.sub(r"-{3,}", "--", chart_code)

        # Prevent mixed chart types (graph + gantt, etc.)
        if "gantt" in chart_code and chart_code.startswith("graph"):
            logging.warning("⚠️ Mixed syntax detected: graph + gantt. Fixing to 'gantt'.")
            chart_code = re.sub(r"^graph\s+\w+", "gantt", chart_code)

        if "graph" in chart_code and "section " in chart_code:
            logging.warning("⚠️ Mixed syntax detected: graph with section. Switching to 'gantt'.")
            chart_code = re.sub(r"^graph\s+\w+", "gantt", chart_code)

        # Enforce correct top-level keywords
        if not any(chart_code.lower().startswith(k) for k in self.valid_keywords):
            chart_code = "graph TD\n" + chart_code

        return chart_code

    # ---------------------------------------------------------------------
    # MAIN CHART GENERATION API
    # ---------------------------------------------------------------------
    def generate_chart(self, chart_type: str, description: str) -> str:
        if not description or not description.strip():
            raise ValueError("Empty description")

        chart_type_lower = chart_type.lower()

        if chart_type_lower == "flowchart":
            return self.generate_flowchart(description)
        elif chart_type_lower == "gantt":
            return self.generate_gantt_chart(description)
        elif chart_type_lower == "sequence":
            return self.generate_sequence_diagram(description)
        elif chart_type_lower == "mindmap":
            return self.generate_mindmap(description)
        elif chart_type_lower == "pie":
            return self.generate_pie_chart(description)
        elif chart_type_lower == "journey":
            return self.generate_user_journey(description)
        elif chart_type_lower == "c4":
            return self.generate_c4_diagram(description)
        else:
            raise ValueError(f"Unsupported chart type: {chart_type}")

    # ---------------------------------------------------------------------
    # SPECIFIC CHART TYPES
    # ---------------------------------------------------------------------
    def generate_flowchart(self, description: str) -> str:
        prompt = f"""
            You are an expert in creating **professional, visually clear, and valid Mermaid.js flowcharts**
            that illustrate **product development or business workflows**. 
            Your goal is to generate a clean, well-structured **top-down flowchart (graph TD)** for the following process:
            {description}

            Follow these design and syntax principles carefully:

            🧩 **STRUCTURE**
            - Always start the diagram with:
                graph TD
            - Use short, meaningful node names (under 6 words).
            - Keep a logical top-to-bottom hierarchy — one clear starting point leading to the final outcome.
            - If there are parallel flows, align them vertically for clarity.
            - Optionally group related steps using **subgraphs** (e.g., “Design Phase”, “Testing Phase”).

            🎨 **VISUAL & STYLE GUIDELINES**
            - Use consistent arrow styles:
                - `-->` for main flow
                - `-.->` for alternate or optional paths
            - Use **rounded nodes** for actions or processes: `([Design])`
            - Use **diamonds** for decisions: `{{Is Approved?}}`
            - Use **rectangles** for data, resources, or milestones: `[Requirement Doc]`
            - Use emojis sparingly to make steps intuitive:
                - 💡 Start / Ideas  
                - 🧩 Design  
                - ⚙️ Development  
                - 🧪 Testing  
                - ✅ Approved  
                - 🚀 Launch  
                - ❌ Rework / Failure
            - Maintain consistent spacing — no crossing or overlapping arrows.

            🧠 **SYNTAX RULES**
            - Use valid Mermaid syntax only.
            - Avoid invalid arrows like `|>`, `=>`, or `==>`.
            - Each node ID should be unique and simple (A, B, C1, etc.).
            - Keep indentation consistent (2 spaces per level).

            ✅ **OUTPUT REQUIREMENTS**
            - Return **only** valid Mermaid code inside triple backticks with `mermaid`.
            - Do **not** include extra commentary, markdown, or explanations.
            - Ensure the flowchart can render cleanly in any Mermaid-compatible viewer.

            Example of the desired professional style:

            ```mermaid
            graph TD
                A[💡 Start: Idea Proposal] --> B[📋 Requirement Analysis]
                B --> C[🧩 Design Prototype]
                C --> D{{Design Approved?}}
                D -->|Yes| E[⚙️ Development Sprint]
                D -->|No| F[🔁 Revise Design]
                E --> G[🧪 QA & Testing]
                G --> H{{All Tests Passed?}}
                H -->|Yes| I[🚀 Deployment]
                H -->|No| J[🐞 Bug Fix Cycle]
                J --> E
                I --> K[✅ Project Sign-off]
            ```

            Now generate a **concise, modern, and professional Mermaid.js flowchart** that clearly visualizes the described process.
            """
        return self._generate_chart(prompt)


    def generate_gantt_chart(self, description: str) -> str:
        prompt = f"""
            You are an expert in creating **visually clean, non-overlapping Mermaid.js Gantt charts**.
            Your job is to generate a **beautiful and readable** Mermaid chart for this project:
            {description}

            Follow these design and syntax rules carefully:

            🧩 **STRUCTURE**
            - Always start with `%%{{init: ...}}%%` to define theme customization.
            - Then start the chart with:
                ```
                gantt
                    title 📅 <Project Title>
                    dateFormat  YYYY-MM-DD
                    axisFormat  %b %d
                    tickInterval 2week
                    excludes weekends
                    todayMarker stroke-width:3px,stroke:#f59e0b
                ```
            - Use 3–5 logical `section` groups (e.g., Discovery, Design, Development, Launch).
            - Each section should have 2–3 concise, readable tasks.

            🎨 **STYLE**
            - Apply a modern, minimal UI using theme variables:
                - primaryColor: "#2563eb"
                - secondaryColor: "#93c5fd"
                - sectionHeaderColor: "#1e3a8a"
                - fontFamily: "Inter, sans-serif"
                - barHeight: 26, barGap: 18, barCornerRadius: 10
                - todayLineColor: "#f59e0b"
            - Include `.taskText`, `.sectionTitle`, and `.today` custom CSS classes.

            🕓 **TASKS**
            - Each task must follow:  
            `Task Name :id, [after <prev_id>|<start_date>], <duration>d`
            - Use durations like 5d, 10d, 3w.
            - Keep task names short (under 30 chars).
            - Avoid overlapping task dates — use “after <id>” sequencing for clarity.

            🧠 **OUTPUT RULES**
            - Return ONLY a **valid, runnable Mermaid code block**.
            - Wrap the code in triple backticks with `mermaid`.
            - Do NOT include explanations, extra text, or markdown outside the code block.

            Example of desired style:
            ```mermaid
            %%{{init: {{
            "theme": "base",
            "themeVariables": {{
                "primaryColor": "#2563eb",
                "secondaryColor": "#93c5fd",
                "tertiaryColor": "#f9fafb",
                "fontFamily": "Inter, sans-serif",
                "fontSize": "14px",
                "taskTextColor": "#0f172a",
                "taskBorderColor": "#2563eb",
                "barHeight": 26,
                "barGap": 18,
                "barCornerRadius": 10,
                "todayLineColor": "#f59e0b",
                "sectionBkgColor": "#f3f4f6",
                "sectionBkgColor2": "#e5e7eb",
                "sectionHeaderColor": "#1e3a8a",
                "sectionHeaderFontWeight": "700",
                "sectionHeaderFontSize": "16px",
                "ganttLeftPadding": 55
            }},
            "themeCSS": "
                .taskText {{ font-weight: 600; fill: #0f172a; }}
                .sectionTitle {{ font-size: 14px; font-weight: 700; fill: #1e3a8a; }}
                .today {{ stroke-width: 3px; stroke-dasharray: 3 3; opacity: 0.8; }}
            "
            }}}}%%

            gantt
                title 📅 2025 Project Roadmap
                dateFormat  YYYY-MM-DD
                axisFormat  %b %d
                tickInterval 2week
                excludes weekends
                todayMarker stroke-width:3px,stroke:#f59e0b

                section Discovery
                Kick-off & Requirements :active, a1, 2025-01-06, 10d
                Approval & Sign-off     :a2, after a1, 5d

                section Design
                UI/UX Prototypes        :crit, a3, after a2, 15d
                Design Review           :a4, after a3, 7d

                section Development
                Backend Setup           :a5, after a4, 25d
                Frontend Integration    :a6, after a5, 20d
                QA & Testing            :a7, after a6, 10d

                section Launch
                UAT & Final Review      :active, a8, after a7, 7d
                Go-Live & Training      :milestone, a9, after a8, 0d
            ```
            """
        return self._generate_chart(prompt)


    def generate_sequence_diagram(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js sequence diagrams.
        Create a valid diagram showing interactions for this scenario:
        {description}

        Rules:
        - Use arrows like `A->>B: Message`.
        - Ensure clear participants and logical flow.
        - Return only valid Mermaid code in ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    def generate_mindmap(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js mindmaps.
        Create a clear mindmap showing hierarchy and relationships:
        {description}

        Rules:
        - Use indentation for hierarchy.
        - Keep node names concise.
        - Return valid Mermaid code in ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    def generate_pie_chart(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js pie charts.
        Create a valid pie chart for the following data:
        {description}

        Example:
        ```mermaid
        pie
            title Resource Allocation
            "Design" : 40
            "Development" : 35
            "Testing" : 25
        ```
        Return valid Mermaid code in ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    def generate_user_journey(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js user journey diagrams.
        Create a valid user journey for this scenario:
        {description}

        Rules:
        - Use proper syntax for journey diagrams.
        - Map emotions, stages, and interactions logically.
        - Return valid Mermaid code in ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    def generate_c4_diagram(self, description: str) -> str:
        prompt = f"""
        You are an expert in creating **C4-style system diagrams** using Mermaid.js.
        Generate a valid Mermaid C4-style diagram for this system:
        {description}

        Rules:
        - Use `graph TD`, subgraphs, and arrows like `A --> B : uses`.
        - Avoid unsupported syntax like `rel()` or `SystemContext`.
        - Return valid Mermaid code in ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    # ---------------------------------------------------------------------
    # MODIFY EXISTING CHART
    # ---------------------------------------------------------------------
    def update_chart(self, modification_prompt: str, current_chart_code: str) -> str:
        prompt = f"""
        You are an expert in editing Mermaid.js diagrams.
        Modify the chart below according to this request:
        "{modification_prompt}"

        Current chart:
        ```mermaid
        {current_chart_code}
        ```

        Return the UPDATED diagram in valid Mermaid syntax inside ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    def fix_chart(self, broken_mermaid_code: str) -> str:
        """Fix broken Mermaid syntax using the LLM."""
        prompt = f"""
        The following Mermaid syntax is broken. Please fix it.

        ```mermaid
        {broken_mermaid_code}
        ```

        Return the corrected diagram in valid Mermaid syntax inside ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    # ---------------------------------------------------------------------
    # AUTOMATION + CLASSIFICATION
    # ---------------------------------------------------------------------
    def suggest_chart_type(self, content: str) -> str:
        """Suggest best diagram type for given content."""
        if not client.api_key:
            return ""

        try:
            chat_completion = client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": f"""
                    You are a diagram classifier.
                    Based on the following content, suggest the most suitable Mermaid.js diagram type.
                    Content: {content}
                    Choose one: flowchart, gantt, sequence, mindmap, pie, user_journey, c4.
                    Reply ONLY with the type name.
                    """
                }],
                temperature=0,
            )
            suggestion = chat_completion.choices[0].message.content.strip().lower()
            return suggestion if suggestion in self.valid_keywords else "none"
        except Exception as e:
            logging.error(f"Error suggesting chart type: {e}")
            return "none"

    def auto_generate_charts_for_proposal(self, sections: list) -> list:
        """Automatically generate diagrams for proposal sections."""
        generated_charts = []
        for section in sections:
            content = getattr(section, "contentHtml", "")
            chart_type = self.suggest_chart_type(content)
            if not chart_type or chart_type == "none":
                continue

            chart_code = self.generate_chart(chart_type, content)
            if chart_code:
                generated_charts.append({
                    "section_id": getattr(section, "id", None),
                    "chart_type": chart_type,
                    "chart_code": chart_code
                })

        return generated_charts
