import base64
import os
import tempfile
import re
import streamlit as st
from utils.document_processor import process_upload
from utils.ai_service import get_gemini_explanation
from utils.patient_data import get_patient_data, validate_field_name, validate_insurance_id

# Configure page
st.set_page_config(
    page_title="Medical AI Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
session_defaults = {
    "messages": [{
        "role": "assistant",
        "content": "I can help with:\n\n* Medical term explanations\n* Insurance information\n* Patient data queries"
    }],
    "current_patient": None,
    "processed_data": {}
}

for key, default in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Sidebar - Patient Management
with st.sidebar:
    st.title("Patient Management")

    # Document Upload
    st.header("Upload Medical Document")
    
    # --- FIX ---
    # The label is now descriptive ("Upload a document") instead of being just instructional text.
    # The label_visibility parameter correctly hides it from the UI.
    uploaded_file = st.file_uploader(
        "Upload a medical document",  # Changed from "Drag and drop file here" to a proper label
        type=["pdf", "png", "jpg", "jpeg"],
        label_visibility="collapsed"
    )

    st.caption("Limit 200MB per file • PDF, PNG, JPG, JPEG")

    # Process uploaded document
    if uploaded_file:
        # Use a temporary directory to handle file paths safely
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            with st.spinner("Processing document..."):
                try:
                    fields, text = process_upload(temp_path)
                    if fields and fields.get("patient_id") != "Not found":
                        patient_id = fields.get("patient_id")
                        st.session_state.processed_data[patient_id] = {
                            "fields": fields,
                            "text": text,
                            "filename": uploaded_file.name
                        }
                        st.session_state.current_patient = patient_id
                        st.success(f"Processed document for Patient {patient_id}")
                    else:
                        st.error("Failed to extract patient ID from document")
                except Exception as e:
                    st.error(f"Error processing document: {str(e)}")

    # Patient Selection
    if st.session_state.processed_data:
        st.header("Select Patient")
        patient_ids = list(st.session_state.processed_data.keys())
        
        # --- FIX ---
        # The empty label "" was replaced with a descriptive label "Select a patient".
        # The label_visibility="collapsed" parameter hides this label visually,
        # but it's available for screen readers, resolving the accessibility warning.
        selected_patient = st.selectbox(
            "Select a patient", # Changed from ""
            patient_ids,
            index=patient_ids.index(st.session_state.current_patient)
            if st.session_state.current_patient in patient_ids else 0,
            label_visibility="collapsed"
        )

        if selected_patient and selected_patient != st.session_state.current_patient:
            st.session_state.current_patient = selected_patient
            st.rerun()

# Main Content
st.title("Medical AI Assistant")

# Patient Overview
if st.session_state.current_patient:
    patient_data = st.session_state.processed_data.get(st.session_state.current_patient)
    if patient_data:
        st.header("Current Patient Overview")
        info_cols = st.columns(3)
        with info_cols[0]:
            st.metric("Name", patient_data["fields"].get("name", "Not found"))
        with info_cols[1]:
            st.metric("Age", patient_data["fields"].get("age", "Not found"))
        with info_cols[2]:
            st.metric("Condition", patient_data["fields"].get("disease", "Not found"))
        with st.expander("View Full Document Text"):
            st.text(patient_data["text"])

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Text Input Processing
prompt = st.chat_input("Ask about medical terms or patient information")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Process query
    query = prompt.strip().lower()
    response = None

    try:
        # Medical term explanation
        if any(keyword in query for keyword in ["medical", "disease", "medicine", "symptom", "diagnosis", "explain", "what is"]):
            prompt_text = f"Explain in 3 sentences: {prompt}. Use WHO definitions and simplify for patients."
            response = get_gemini_explanation(prompt_text)

        # Insurance term explanation
        elif any(keyword in query for keyword in ["insurance", "policy", "claim", "deductible", "coverage", "premium"]):
            prompt_text = f"Explain insurance aspect: {prompt}. Cross-reference with Medicare guidelines."
            response = get_gemini_explanation(prompt_text)

        # Patient data retrieval
        elif any(keyword in query for keyword in ["data", "info", "details", "patient", "record", "get", "show", "find"]):
            # Look for insurance ID pattern in the query
            insurance_id_match = re.search(r'\b[A-Za-z0-9-]{3,}\b', query)
            if insurance_id_match:
                insurance_id = insurance_id_match.group(0)
                if not validate_insurance_id(insurance_id):
                    response = "Invalid Insurance ID format. Please use alphanumeric characters and hyphens only."
                else:
                    # Look for field name in the query
                    field_match = re.search(
                        r'\b(name|father|aadhar|gender|blood|address|hospital|phone|disease|medicines|medication|bed|amount|charges)\b',
                        query,
                        re.IGNORECASE
                    )
                    if field_match:
                        field = field_match.group(0).lower()
                        if field == "medication":
                            field = "medicines"  # Normalize field name
                        if validate_field_name(field):
                            response = get_patient_data(insurance_id, field)
                        else:
                            response = "Invalid field name. Please specify: name, father, aadhar, gender, blood, address, hospital, phone, disease, medicines, bed, amount, or charges."
                    else:
                        response = "Please specify what information you need (e.g., name, address, disease, medicines, etc.)"
            else:
                # Check if we have a current patient selected
                if st.session_state.current_patient:
                    field_match = re.search(
                        r'\b(name|father|aadhar|gender|blood|address|hospital|phone|disease|medicines|medication|bed|amount|charges)\b',
                        query,
                        re.IGNORECASE
                    )
                    if field_match:
                        field = field_match.group(0).lower()
                        if field == "medication":
                            field = "medicines"
                        if validate_field_name(field):
                            response = get_patient_data(st.session_state.current_patient, field)
                        else:
                            response = "Invalid field name."
                    else:
                        response = f"Current patient: {st.session_state.current_patient}. Please specify what information you need."
                else:
                    response = "Please provide an Insurance ID or upload a document first."

        # General chat or fallback response
        else:
            response = get_gemini_explanation(f"Respond as a helpful medical AI assistant: {prompt}")

    except Exception as e:
        response = f"Sorry, I encountered an error: {str(e)}. Please try again."

    # Ensure we have a response
    if not response:
        response = "I can help explain medical/insurance terms or retrieve patient data. Please clarify your request."

    # Display response
    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
