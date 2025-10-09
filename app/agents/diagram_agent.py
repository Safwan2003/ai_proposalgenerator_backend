import os
import re
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class DiagramAgent:
    def __init__(self):
        self.valid_keywords = [
            "graph", "gantt", "pie", "sequence", "mindmap", "journey", "c4"
        ]
        self.model = "llama-3.3-70b-versatile"

    def _generate_chart(self, prompt: str, retries: int = 2) -> str:
        """Generate a diagram using Groq and extract Mermaid code."""
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

                # Extract mermaid code block
                match = re.search(r"```mermaid\s*(.*?)```", response_content, re.DOTALL)
                if match:
                    chart_code = match.group(1).strip()
                    if any(chart_code.lower().startswith(k) for k in self.valid_keywords):
                        # Fix invalid arrow syntax if present
                        chart_code = re.sub(r"\|>+", "|", chart_code)
                        chart_code = re.sub(r"-{3,}", "--", chart_code)
                        return chart_code

            except Exception as e:
                print(f"Error generating chart (attempt {attempt + 1}): {e}")
                time.sleep(1)

        return ""

    # ----------------- DIAGRAM TYPES -----------------
    def generate_flowchart(self, description: str) -> str:
        prompt = f"""
        You are an expert in creating **valid Mermaid.js flowcharts**.
        Generate a `graph TD` diagram for the following process:
        {description}

        Requirements:
        - Use valid Mermaid syntax only.
        - Use --> for connections, never |>| or unusual arrows.
        - Avoid special characters in node IDs.
        - Return ONLY the Mermaid code inside ```mermaid ... ```.
        """
        return self._generate_chart(prompt)

    def generate_gantt_chart(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js Gantt charts.
        Create a valid Gantt chart for this project:
        {description}

        Notes:
        - Include `dateFormat  YYYY-MM-DD`.
        - Group tasks under relevant sections.
        - All tasks should have start date and duration.
        - Return only valid Mermaid Gantt syntax in ```mermaid ... ```.
        """
        return self._generate_chart(prompt)

    def generate_sequence_diagram(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js sequence diagrams.
        Create a valid sequence diagram for this scenario:
        {description}

        Notes:
        - Use simple participants and arrows like A->>B.
        - Ensure valid indentation and structure.
        - Return only valid Mermaid code in ```mermaid ... ```.
        """
        return self._generate_chart(prompt)

    def generate_mindmap(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js mindmaps.
        Create a valid mindmap from this content:
        {description}

        Notes:
        - Use indentation for hierarchy.
        - Keep node names simple.
        - Return only valid Mermaid mindmap code in ```mermaid ... ```.
        """
        return self._generate_chart(prompt)

    def generate_pie_chart(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js pie charts.
        Create a valid pie chart from this information:
        {description}

        Example format:
        ```mermaid
        pie
            title Resource Allocation
            "Design" : 40
            "Development" : 35
            "Testing" : 25
        ```
        Return only valid Mermaid code inside ```mermaid ... ```.
        """
        return self._generate_chart(prompt)

    def generate_user_journey(self, description: str) -> str:
        prompt = f"""
        You are an expert in Mermaid.js user journey diagrams.
        Create a valid user journey chart for this scenario:
        {description}

        Notes:
        - Follow correct Mermaid syntax for journey charts.
        - Use logical user emotions and stages.
        - Return only Mermaid code.
        """
        return self._generate_chart(prompt)

    def generate_c4_diagram(self, description: str) -> str:
        prompt = f"""
        You are an expert in **C4-style system diagrams using Mermaid.js**.
        Generate a valid **Mermaid C4 diagram** for this system description:
        {description}
        ⚠️ Strict rules:
        - Mermaid.js does **not** support "System Context" or "rel()" syntax.
        - Use **graph TD**, subgraphs, and simple arrows --> instead.
        - Represent relationships like `A --> B : uses`.
        - Use descriptive labels.
        - Return only valid Mermaid code enclosed in ```mermaid ... ```.

        Example:
        ```mermaid
        graph TD
            User[User] -->|Uses| App[Web App]
            App -->|Reads/Writes| Database[(DB)]
        Return only valid Mermaid.js syntax inside ```mermaid ... ```.
        """
        return self._generate_chart(prompt)

    def update_chart(self, modification_prompt: str, current_chart_code: str) -> str:
        prompt = f"""
        You are an expert in updating Mermaid.js diagrams.
        Modify the following chart based on the user's request.

        Request: "{modification_prompt}"

        Current chart:
        ```mermaid
        {current_chart_code}
        ```

        Return the UPDATED chart in valid Mermaid syntax.
        """
        return self._generate_chart(prompt)

    # ----------------- SUGGESTION + AUTOMATION -----------------
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
                    You are an expert diagram classifier.
                    Based on the following content, suggest the best Mermaid.js diagram type.
                    Content: {content}
                    Choose one from: flowchart, gantt, sequence, mindmap, pie, user_journey, c4.
                    Reply ONLY with the type name (e.g., flowchart).
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
        """Auto-generate diagrams for proposal sections."""
        generated_charts = []
        for section in sections:
            chart_type = self.suggest_chart_type(getattr(section, "contentHtml", ""))
            if not chart_type or chart_type == "none":
                continue

            content = getattr(section, "contentHtml", "")
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


# Create reusable instance
diagram_agent = DiagramAgent()
