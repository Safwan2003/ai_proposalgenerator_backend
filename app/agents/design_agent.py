import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

class DesignAgent:
    def get_design_suggestions(self, proposal) -> list:
        if not client:
            return []

        prompt = f"""
        As an expert UI/UX designer, your task is to generate a list of design suggestions for a business proposal.
        The proposal content is as follows:
        {proposal.sections}

        Based on the content, generate a list of 3-5 design suggestions. Each suggestion should be a JSON object with the following keys:
        - `prompt`: A short, descriptive prompt for the design (e.g., "A modern, minimalist design with a blue color scheme").
        - `css`: The CSS code for the design.

        Return a valid JSON array of design suggestion objects.
        """

        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
            )
            response_content = chat_completion.choices[0].message.content
            return json.loads(response_content)
        except Exception as e:
            print(f"Error generating design suggestions: {e}")
            return []

design_agent = DesignAgent()
