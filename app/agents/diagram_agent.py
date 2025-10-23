import os
import re
import time
from groq import Groq

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class DiagramAgent:
    def __init__(self):
        self.valid_keywords = [
            "graph", "gantt", "pie", "sequence", "mindmap", "journey", "c4"
        ]
        self.model = os.environ.get("GROQ_DIAGRAM_MODEL_NAME", "mixtral-8x7b-32768")

    # ---------------------------------------------------------------------
    # CORE GENERATOR
    # ---------------------------------------------------------------------
    def _generate_chart(self, prompt: str, retries: int = 2) -> str:
        """Generate a diagram using Groq and extract valid Mermaid code."""
        if not client.api_key:
            print("⚠️ Missing GROQ_API_KEY.")
            return ""

        for attempt in range(retries):
            try:
                chat_completion = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=1024,
                )

                response_content = chat_completion.choices[0].message.content
                if not response_content:
                    continue

                # Extract mermaid code
                match = re.search(r"```mermaid\s*(.*?)```", response_content, re.DOTALL)
                if not match:
                    continue

                chart_code = match.group(1).strip()

                # Sanitize and validate chart type
                chart_code = self._sanitize_chart_code(chart_code)

                if any(chart_code.lower().startswith(k) for k in self.valid_keywords):
                    return chart_code

            except Exception as e:
                print(f"Error generating chart (attempt {attempt + 1}): {e}")
                time.sleep(1)

        return ""

    # ---------------------------------------------------------------------
    # SANITIZER
    # ---------------------------------------------------------------------
    def _sanitize_chart_code(self, chart_code: str) -> str:
        """Fix invalid Mermaid syntax automatically."""
        # Fix invalid arrows and syntax artifacts
        chart_code = re.sub(r"\|>+", "|", chart_code)
        chart_code = re.sub(r"-{3,}", "--", chart_code)

        # Prevent mixed chart types (graph + gantt, etc.)
        if "gantt" in chart_code and chart_code.startswith("graph"):
            print("⚠️ Mixed syntax detected: graph + gantt. Fixing to 'gantt'.")
            chart_code = re.sub(r"^graph\s+\w+", "gantt", chart_code)

        if "graph" in chart_code and "section " in chart_code:
            print("⚠️ Mixed syntax detected: graph with section. Switching to 'gantt'.")
            chart_code = re.sub(r"^graph\s+\w+", "gantt", chart_code)

        # Enforce correct top-level keywords
        if not any(chart_code.lower().startswith(k) for k in self.valid_keywords):
            # Default to flowchart if uncertain
            chart_code = "graph TD\n" + chart_code

        return chart_code

    # ---------------------------------------------------------------------
    # DIAGRAM TYPES
    # ---------------------------------------------------------------------
    def generate_flowchart(self, description: str) -> str:
        prompt = f"""
        You are an expert in creating **valid Mermaid.js flowcharts**.
        Generate a `graph TD` diagram for the following process:
        {description}

        Rules:
        - Use valid Mermaid syntax only.
        - Use `-->` for connections, never `|>` or nonstandard arrows.
        - Avoid special characters in node IDs.
        - Return ONLY the Mermaid code inside ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    def generate_gantt_chart(self, description: str) -> str:
        prompt = f"""
        You are an expert in creating **valid and simple Mermaid.js Gantt charts**.
        Create a valid Gantt chart for this project description:
        {description}

        **CRITICAL RULES:**
        1.  The syntax MUST be simple.
        2.  Each task line must follow this exact format: `Task Name :[optional_id], yyyy-mm-dd, DURATION`.
        3.  **DO NOT** use any other syntax like `taskData`, functions, or complex IDs. The format is strict.
        4.  Start with `gantt` and include `dateFormat YYYY-MM-DD`.
        5.  Use `section` for grouping tasks.

        Return ONLY the valid Mermaid code inside ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    def generate_sequence_diagram(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js sequence diagrams.
        Create a valid diagram showing interactions for this scenario:
        {description}

        Rules:
        - Use standard arrows like `A->>B: Message`.
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
        - Use indentation to represent hierarchy.
        - Keep node names concise.
        - Return only valid Mermaid mindmap code in ```mermaid ... ``` blocks.
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
        Return only valid Mermaid code in ```mermaid ... ``` blocks.
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
        - Return only valid Mermaid code in ```mermaid ... ``` blocks.
        """
        return self._generate_chart(prompt)

    def generate_c4_diagram(self, description: str) -> str:
        prompt = f"""
        You are an expert in creating **C4-style system diagrams** using Mermaid.js.
        Generate a valid Mermaid C4-style diagram for this system:
        {description}

        ⚠️ Rules:
        - Use `graph TD`, subgraphs, and arrows like `A --> B : uses`.
        - Avoid unsupported C4 syntax like `rel()` or `SystemContext`.
        - Use descriptive labels.
        - Return only valid Mermaid code in ```mermaid ... ``` blocks.
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
        """Fixes broken Mermaid syntax using the LLM."""
        prompt = f"""
        The following Mermaid syntax is broken and will not render. Please fix it.

        Broken Syntax:
        ```mermaid
        {{broken_mermaid_code}}
        ```

        Return the UPDATED diagram in valid Mermaid syntax inside ```mermaid ... ``` blocks.
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
            print(f"Error suggesting chart type: {e}")
            return "none"

    def auto_generate_charts_for_proposal(self, sections: list) -> list:
        """Automatically generate diagrams for proposal sections."""
        generated_charts = []
        for section in sections:
            content = getattr(section, "contentHtml", "")
            chart_type = self.suggest_chart_type(content)
            if not chart_type or chart_type == "none":
                continue

            chart_code = ""

            if chart_type == "flowchart":
                chart_code = self.generate_flowchart(content)
            elif chart_type == "gantt":
                chart_code = self.generate_gantt_chart(content)
            elif chart_type == "sequence":
                chart_code = self.generate_sequence_diagram(content)
            elif chart_type == "mindmap":
                chart_code = self.generate_mindmap(content)
            elif chart_type == "pie":
                chart_code = self.generate_pie_chart(content)
            elif chart_type == "user_journey":
                chart_code = self.generate_user_journey(content)
            elif chart_type == "c4":
                chart_code = self.generate_c4_diagram(content)

            if chart_code:
                generated_charts.append({
                    "section_id": getattr(section, "id", None),
                    "chart_type": chart_type,
                    "chart_code": chart_code
                })

        return generated_charts


# ✅ Create reusable instance
diagram_agent = DiagramAgent()
