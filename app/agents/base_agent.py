import os
import logging
import re
from groq import Groq
from app.core.config import settings
from typing import List, Dict

class ConversableAgent:
    """A base class for AI agents that can converse with each other."""

    def __init__(self, name: str, system_message: str, client: Groq, model: str = settings.GROQ_MODEL_DEFAULT):
        self.name = name
        self.system_message = system_message
        self.model = model
        self.client = client

    def get_image_query_from_text(self, text: str) -> str:
        """Extract keywords from a text to be used as an image query."""
        if not self.client or not text or text.isspace():
            return ""

        if not isinstance(text, str):
            logging.warning(f"Input to get_image_query_from_text is not a string: {text}")
            return ""

        # Truncate the text to the first 500 characters to avoid overly long prompts
        truncated_text = text[:500]

        prompt = f"""Analyze the following text and extract a concise, 3-5 word image search query that visually represents the core concepts.

        **Instructions:**
        1.  **Think Visually:** Focus on concrete objects, actions, and metaphors described in the text.
        2.  **Be Specific:** Instead of "business", think "team collaborating office". Instead of "data", think "glowing data network".
        3.  **Format:** Return ONLY the keywords as a single, lowercase, space-separated string. Do not use punctuation.

        **Text to Analyze:**
        "{truncated_text}"

        **Search Query:**
        """

        try:
            resp = self.client.chat.completions.create(
                model=settings.GROQ_MODEL_DEFAULT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2, # Lower temperature for more focused output
            )
            keywords = resp.choices[0].message.content.strip().lower()
            
            # Add a check to ensure the returned keywords are not too long
            if len(keywords) > 75:
                logging.warning(f"Returned keywords are too long: {keywords}")
                return ""

            return keywords.strip()
        except Exception as e:
            logging.error(f"Error extracting keywords from text: {e}")
            return ""

    def generate_response(self, message_history: List[Dict]) -> str:
        """Generate a response based on the message history."""
        if not self.client:
            logging.warning("⚠️ Missing GROQ_API_KEY.")
            return ""

        messages = [
            {"role": "system", "content": self.system_message},
            message_history[-1], # Only send the last user message
        ]

        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )

            response = chat_completion.choices[0].message.content
            logging.info(f"✅ Agent '{self.name}' generated response: {response[:100]}...")
            return response

        except Exception as e:
            logging.error(f"Error generating response from agent '{self.name}': {e}")
            return ""

    def log_conversation(self, message_history: List[Dict], agent_name: str):
        """Logs the conversation history in a readable format."""
        logging.info(f"--- Conversation with {agent_name} ---")
        for message in message_history:
            logging.info(f"  {message['role'].capitalize()}: {message['content']}")
        logging.info(f"--- End of Conversation with {agent_name} ---")
