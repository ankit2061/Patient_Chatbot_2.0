import re
import streamlit as st

# Mock data for testing
MOCK_PATIENT_DATA = {
    "12345": {
        "name": "John Doe",
        "father": "Robert Doe",
        "aadhar": "1234-5678-9012",
        "gender": "Male",
        "blood": "O+",
        "address": "123 Main St, Anytown, USA",
        "hospital": "General Hospital",
        "phone": "555-123-4567",
        "disease": "Hypertension",
        "medicines": "Lisinopril, Amlodipine",
        "bed": "Room 302, Bed 1",
        "amount": "5000",
        "charges": "500"
    },
    "67890": {
        "name": "Jane Smith",
        "father": "David Smith",
        "aadhar": "9876-5432-1098",
        "gender": "Female",
        "blood": "A-",
        "address": "456 Oak St, Othertown, USA",
        "hospital": "Community Medical Center",
        "phone": "555-987-6543",
        "disease": "Diabetes",
        "medicines": "Metformin, Insulin",
        "bed": "Room 205, Bed 2",
        "amount": "6500",
        "charges": "650"
    }
}

def handle_errors(func):
    """Error handling decorator for patient data functions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            st.error(f"Error: {e}")
            return f"Error retrieving patient data: {str(e)}"
    return wrapper

# Input Validation Functions
def validate_insurance_id(insurance_id):
    """Validate the format of insurance ID"""
    return re.match(r'^[A-Za-z0-9-]+$', insurance_id) is not None

def validate_field_name(field):
    """Validate that the requested field is valid"""
    valid_fields = ["name", "father", "aadhar", "gender", "blood",
                   "address", "hospital", "phone", "disease",
                   "medicines", "bed", "amount", "charges"]
    return field.lower() in valid_fields

@handle_errors
def get_patient_data(insurance_id, field):
    """Get patient data from mock database or processed documents"""
    
    # Check if insurance ID exists in mock data
    if insurance_id in MOCK_PATIENT_DATA and field in MOCK_PATIENT_DATA[insurance_id]:
        return MOCK_PATIENT_DATA[insurance_id][field]
    
    # Check if insurance ID exists in processed data
    elif insurance_id in st.session_state.processed_data:
        patient_data = st.session_state.processed_data[insurance_id]
        
        # Check if field exists in extracted fields
        if field in patient_data["fields"]:
            return patient_data["fields"][field]
        
        # If the field isn't in extracted fields, try to find it in the text using regex
        elif "text" in patient_data:
            text = patient_data["text"]
            patterns = {
                "name": r"Name:\s*([^\n]+)",
                "father": r"Father('s)? Name:\s*([^\n]+)",
                "aadhar": r"Aadhar( Number)?:\s*([^\n]+)",
                "gender": r"Gender:\s*([^\n]+)",
                "blood": r"Blood( Group)?:\s*([^\n]+)",
                "address": r"Address:\s*([^\n]+)",
                "hospital": r"Hospital( Name)?:\s*([^\n]+)",
                "phone": r"(Phone|Contact)( Number)?:\s*([^\n]+)",
                "disease": r"(Disease|Condition|Diagnosis):\s*([^\n]+)",
                "medicines": r"(Medicines|Medications|Drugs):\s*([^\n]+)",
                "bed": r"Bed( Number)?:\s*([^\n]+)",
                "amount": r"Amount:\s*([^\n]+)",
                "charges": r"Charges:\s*([^\n]+)"
            }
            
            if field in patterns:
                match = re.search(patterns[field], text, re.IGNORECASE)
                if match:
                    # Use the last capture group
                    return match.group(len(match.groups())).strip()
    
    # If we get here, the data was not found
    return "Data not found for this patient."
