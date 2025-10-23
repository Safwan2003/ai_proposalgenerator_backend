import os
from typing import List
from groq import Groq

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

class AutomationAgent:
    def get_smart_suggestions(self, context: str) -> List[str]:
        """Provide smart suggestions based on the context using an LLM."""
        prompt = f"""
        Given the following text from a business proposal, provide three concise, actionable suggestions for improvement.
        Return the suggestions as a JSON array of strings.

        Proposal Text:
        "{context}"

        Suggestions:
        """
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=os.environ.get("GROQ_DEFAULT_MODEL_NAME", "llama-3.1-8b-instant"),
                temperature=0.7,
            )
            suggestions = chat_completion.choices[0].message.content
            # Assuming the model returns a JSON array string, parse it.
            # This might need more robust error handling in a real app.
            import json
            return json.loads(suggestions)
        except Exception as e:
            print(f"Error generating smart suggestions: {e}")
            # Fallback to generic suggestions
            return [
                "Suggestion: Ensure the language is client-focused.",
                "Suggestion: Add data or metrics to support claims.",
                "Suggestion: Check for clarity and conciseness."
            ]

    def expand_bullet_points(self, bullet_points: List[str]) -> str:
        """Expand a list of bullet points into a full paragraph using an LLM."""
        bullets_str = "\n".join(f"- {bp}" for bp in bullet_points)
        prompt = f"""
        Expand the following bullet points into a cohesive and professional paragraph.

        Bullet Points:
        {bullets_str}

        Expanded Paragraph:
        """
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.1-8b-instant",
                temperature=0.6,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Error expanding bullet points: {e}")
            return "Could not expand bullet points due to an error."

automation_agent = AutomationAgent()