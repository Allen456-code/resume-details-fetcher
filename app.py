import fitz  # PyMuPDF
import docx
import re
import spacy
import pandas as pd
import streamlit as st
import json

# OCR imports
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# -------- PDF Text Extraction (Normal) --------
def extract_text_from_pdf(pdf_file):
    pdf_file.seek(0)
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text("text")
    return text

# -------- PDF Text Extraction (OCR for scanned PDFs) --------
def extract_text_from_pdf_ocr(pdf_file):
    pdf_file.seek(0)
    images = convert_from_bytes(pdf_file.read())
    text = ""
    for image in images:
        text += pytesseract.image_to_string(image)
    return text

# -------- DOCX Text Extraction --------
def extract_text_from_docx(docx_file):
    doc = docx.Document(docx_file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# -------- Section Extraction (Regex) --------
def extract_sections(text):
    data = {}

    # Skills
    skills_pattern = r"(Skills|Technical Skills)[:\n](.*?)(\n\n|$)"
    skills = re.findall(skills_pattern, text, re.IGNORECASE | re.DOTALL)
    if skills:
        data["Skills"] = skills[0][1].replace("\n", ", ").strip()

    # Education
    education_pattern = r"(B\.?Tech|B\.?Sc|M\.?Sc|MBA|M\.?Tech|Bachelor|Master|Ph\.?D)[^\n]*"
    education = re.findall(education_pattern, text, re.IGNORECASE)
    if education:
        data["Education"] = list(set([edu.strip() for edu in education]))

    # Experience
    exp_pattern = r"(Experience|Work Experience|Employment History)[:\n](.*?)(\n\n|$)"
    experience = re.findall(exp_pattern, text, re.IGNORECASE | re.DOTALL)
    if experience:
        data["Experience"] = experience[0][1].replace("\n", " ").strip()

    # Email
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    emails = re.findall(email_pattern, text)
    if emails:
        data["Email"] = emails[0]

    # Phone number
    phone_pattern = r"(\+?\d{1,3}[\s-]?)?\d{10}\b"
    phones = re.findall(phone_pattern, text.replace(" ", ""))
    if phones:
        data["Phone"] = phones[0]

    return data

# -------- Named Entity Recognition (spaCy) --------
def extract_entities(text):
    doc = nlp(text)
    entities = {"Name": None, "Organizations": [], "Dates": []}

    for ent in doc.ents:
        if ent.label_ == "PERSON" and entities["Name"] is None:
            entities["Name"] = ent.text
        elif ent.label_ == "ORG":
            entities["Organizations"].append(ent.text)
        elif ent.label_ == "DATE":
            entities["Dates"].append(ent.text)

    # Fallback: first 5 lines
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not entities["Name"] and lines:
        for line in lines[:5]:
            if line.lower() not in ["resume", "cv", "curriculum vitae"]:
                entities["Name"] = line
                break

    entities["Organizations"] = list(set(entities["Organizations"]))
    entities["Dates"] = list(set(entities["Dates"]))

    return entities

# -------- Streamlit UI --------
def main():
    st.title("📄 Smart Resume Parser (PDF & DOCX, OCR Supported)")
    st.write("Upload a resume to extract structured information.")

    uploaded_file = st.file_uploader("Upload Resume", type=["pdf", "docx"])

    if uploaded_file is not None:
        # Extract text based on file type
        if uploaded_file.name.lower().endswith(".pdf"):
            text = extract_text_from_pdf(uploaded_file)
            if not text.strip():
                st.warning("PDF may be scanned. Using OCR...")
                text = extract_text_from_pdf_ocr(uploaded_file)
        elif uploaded_file.name.lower().endswith(".docx"):
            text = extract_text_from_docx(uploaded_file)
        else:
            st.error("Unsupported file format")
            return

        if not text.strip():
            st.warning("No text could be extracted from this file.")
            return

        # Show preview
        st.subheader("Extracted Text (Preview)")
        st.text(text[:500] + "..." if len(text) > 500 else text)

        # Parse sections and entities
        sections = extract_sections(text)
        entities = extract_entities(text)
        result = {**sections, **entities}

        st.subheader("Parsed Resume Data")
        st.json(result)

        # Export CSV & JSON
        df = pd.DataFrame({k: [", ".join(v) if isinstance(v, list) else v] for k, v in result.items()})

        st.download_button(
            label="📥 Download as CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="parsed_resume.csv",
            mime="text/csv",
        )

        st.download_button(
            label="📥 Download as JSON",
            data=json.dumps(result, indent=4).encode("utf-8"),
            file_name="parsed_resume.json",
            mime="application/json",
        )

if __name__ == "__main__":
    main()