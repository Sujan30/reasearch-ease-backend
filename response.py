from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client with API key
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def generateResponse(user_query, retrieved_chunks):
    """Passes retrieved text chunks into GPT-4 to generate a structured response."""
    
    # Combine research snippets
    context = '\n\n'.join(retrieved_chunks)
    
    # Define the system prompt
    prompt = f"""
    You are an AI research assistant helping a researcher understand a research paper.
    Answer the following question using the given research context:

    Research Context:
    {context}

    User Question: {user_query}

    Provide a well-structured and concise response.
    You will also provide relevant citations from the research paper.
    """
    
    # Call GPT-4 (or GPT-3.5-turbo) API
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}]
    )
    
    return response.choices[0].message.content  # Correctly extract the response