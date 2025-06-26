import os
import google.generativeai as genai
import streamlit as st

# Configure Google Gemini API
# Get API key from environment or use the provided one as fallback
def configure_genai():
    """Configure the Google Generative AI API with the API key from Streamlit secrets"""
    api_key = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=api_key)

# Configure Gemini on module import
configure_genai()

def handle_errors(func):
    """Error handling decorator for AI functions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            st.error(f"Error: {e}")
            return f"AI service error: {str(e)}"
    return wrapper

@handle_errors
# def get_gemini_explanation(prompt):
#     """Get explanations from Google Gemini AI"""
#     try:
#         # Use gemini-1.5-flash for fast responses
#         model = genai.GenerativeModel('gemini-1.5-flash')
        
#         # Enhance the prompt with specific instructions for better responses
#         enhanced_prompt = f"""
#         You are a medical AI assistant helping patients understand medical and insurance terms.
#         Please provide a clear, accurate, and concise explanation of:
        
#         {prompt}
        
#         Keep your response factual, ethical, and patient-friendly. Avoid speculation.
#         """
        
#         response = model.generate_content(enhanced_prompt)
#         return response.text
#     except Exception as e:
#         return f"Gemini API Error: {e}"

def get_gemini_explanation(prompt, audio_data=None):
    model = genai.GenerativeModel('gemini-2.5-flash')  # Updated model
    enhanced_prompt = f"""
**ROLE**: Medical AI assistant specializing in insurance and patient data
**TASK**: {prompt}
**THINKING PROCESS**:
1. Analyze whether query requires medical/insurance explanation or data retrieval
2. For medical terms: Use WHO definitions and simplify for patients
3. For insurance: Cross-reference with Medicare guidelines
4. For patient data: Verify session state context first
**OUTPUT GUIDELINES**:
- 3 sentence maximum for explanations
- Prioritize accuracy over creativity
- Never speculate beyond source materials
"""
    if audio_data:
        audio_file = genai.upload_file(audio_data)
        response = model.generate_content([enhanced_prompt, audio_file])
    else:
        response = model.generate_content(enhanced_prompt)
    return response.text
