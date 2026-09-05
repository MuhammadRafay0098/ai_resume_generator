import os
import re
import json
import warnings
import logging
import streamlit as st
from groq import Groq
from fpdf import FPDF

# Suppress warnings
warnings.filterwarnings('ignore')
logging.getLogger('streamlit').setLevel(logging.CRITICAL)

# Streamlit Page Config
st.set_page_config(
    page_title="AI Resume Generator",
    page_icon="📄",
    layout="wide"
)

# Initialize Groq Client using Streamlit Secrets or Environment Variables
@st.cache_resource
def init_groq_client():
    api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("❌ GROQ_API_KEY not found! Please add it to Streamlit Secrets.")
        st.stop()
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Failed to initialize Groq: {str(e)}")
        st.stop()

class ResumePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)

    def clean_text(self, text):
        if not text:
            return ""
        text = str(text).replace("•", "-").replace("—", "-").replace("–", "-")
        return text.encode('latin-1', 'replace').decode('latin-1').strip()

    def add_section_header(self, title):
        eff_width = self.w - self.l_margin - self.r_margin
        self.ln(3)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(26, 82, 118)
        self.cell(eff_width, 6, title.upper(), 0, 1, 'L')
        self.set_draw_color(214, 219, 223)
        self.set_line_width(0.4)  # Corrected method name
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def create_resume(self, content, user_data):
        self.add_page()
        eff_width = self.w - self.l_margin - self.r_margin

        # Header
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(33, 47, 60)
        name = self.clean_text(user_data.get('name', ''))
        self.cell(eff_width, 10, name, 0, 1, 'C')

        # Contact Bar
        self.set_font('Helvetica', '', 9)
        self.set_text_color(100, 110, 120)
        contact_items = []
        if user_data.get('email'): contact_items.append(self.clean_text(user_data['email']))
        if user_data.get('phone'): contact_items.append(self.clean_text(user_data['phone']))
        if user_data.get('linkedin'): contact_items.append(self.clean_text(user_data['linkedin']))
        
        if contact_items:
            self.cell(eff_width, 5, '  |  '.join(contact_items), 0, 1, 'C')
        self.ln(2)

        # Summary
        summary_text = self.clean_text(content.get('summary', ''))
        if summary_text:
            self.add_section_header("Professional Summary")
            self.set_font('Helvetica', '', 9.5)
            self.set_text_color(44, 62, 80)
            self.multi_cell(eff_width, 4.5, summary_text)

        # Work Experience
        if content.get('experience'):
            self.add_section_header("Work Experience")
            for exp in content['experience']:
                title = self.clean_text(exp.get('title', ''))
                company = self.clean_text(exp.get('company', ''))
                period = self.clean_text(exp.get('period', ''))

                self.set_font('Helvetica', 'B', 10)
                self.set_text_color(33, 47, 60)
                
                header_title = f"{title} - {company}" if company else title
                date_width = 45 if period else 0
                title_width = eff_width - date_width

                self.cell(title_width, 5, header_title, 0, 0, 'L')
                if period:
                    self.set_font('Helvetica', 'I', 9)
                    self.set_text_color(127, 140, 141)
                    self.cell(date_width, 5, period, 0, 1, 'R')
                else:
                    self.ln(5)

                self.set_font('Helvetica', '', 9.5)
                self.set_text_color(44, 62, 80)
                for resp in exp.get('responsibilities', []):
                    clean_resp = self.clean_text(resp)
                    if clean_resp:
                        self.set_x(self.l_margin)
                        self.cell(5, 4.5, "-", 0, 0, 'C')
                        self.multi_cell(eff_width - 5, 4.5, clean_resp)
                self.ln(2)

        # Education
        if content.get('education'):
            self.add_section_header("Education")
            self.set_font('Helvetica', '', 9.5)
            self.set_text_color(44, 62, 80)
            for edu in content['education']:
                clean_edu = self.clean_text(edu)
                if clean_edu:
                    self.set_x(self.l_margin)
                    self.cell(5, 4.5, "-", 0, 0, 'C')
                    self.multi_cell(eff_width - 5, 4.5, clean_edu)
            self.ln(2)

        # Skills
        if content.get('skills'):
            self.add_section_header("Skills")
            self.set_font('Helvetica', '', 9.5)
            self.set_text_color(44, 62, 80)
            skills_list = [self.clean_text(s) for s in content['skills'] if s]
            skills_text = ', '.join(skills_list)
            self.multi_cell(eff_width, 4.5, skills_text)


class ResumeGenerator:
    def __init__(self):
        self.client = init_groq_client()
        self.model = "openai/gpt-oss-20b"

    def generate_resume_content(self, data):
        prompt = f"""
You must output a strictly valid JSON object. Do not include extra commentary or quotes around the response.

Candidate details:
- Name: {data.get('name', '')}
- Email: {data.get('email', '')}
- Phone: {data.get('phone', '')}
- LinkedIn: {data.get('linkedin', '')}
- Experience: {data.get('experience', '')}
- Education: {data.get('education', '')}
- Skills: {data.get('skills', '')}
- Projects: {data.get('projects', '')}

Output JSON structure:
{{
    "summary": "Professional summary paragraph.",
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "period": "Start - End Date",
            "responsibilities": ["Responsibility bullet 1", "Responsibility bullet 2"]
        }}
    ],
    "education": ["Degree details"],
    "skills": ["Skill 1", "Skill 2"]
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a specialized JSON resume builder. You always respond with a single valid JSON object containing summary, experience, education, and skills."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
            return json.loads(raw_content)
        except Exception as e:
            st.error(f"AI Generation Error: {str(e)}")
            return self.get_default_resume(data)

    def get_default_resume(self, data):
        return {
            "summary": f"Results-driven professional with experience in {data.get('skills', 'core domain skills')}.",
            "experience": [
                {
                    "title": "Professional Role",
                    "company": "Organization",
                    "period": "Recent",
                    "responsibilities": [data.get('experience', 'Managed core operations.')]
                }
            ],
            "education": [data.get('education', 'Academic Qualification')],
            "skills": [s.strip() for s in data.get('skills', '').split(',') if s.strip()] or ["General Skills"]
        }

def main():
    st.title("📄 AI Resume Generator")
    
    with st.sidebar:
        st.markdown("### Model Active")
        st.info("GPT OSS 20B (Groq Free Tier)")
    
    with st.expander("Personal Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name *")
            email = st.text_input("Email *")
        with col2:
            phone = st.text_input("Phone *")
            linkedin = st.text_input("LinkedIn")
    
    experience = st.text_area("Work Experience *", height=120)
    education = st.text_area("Education *", height=80)
    skills = st.text_area("Skills *", height=60)
    projects = st.text_area("Projects", height=80)
    
    if st.button("Generate Resume", type="primary", use_container_width=True):
        user_data = {
            'name': name, 'email': email, 'phone': phone,
            'linkedin': linkedin,
            'experience': experience, 'education': education,
            'skills': skills, 'projects': projects
        }
        
        missing = [k for k in ['name', 'email', 'phone', 'experience', 'education', 'skills'] if not user_data[k]]
        if missing:
            st.error(f"Please fill in required fields: {', '.join(missing)}")
            return
        
        with st.spinner("Generating ATS Resume..."):
            generator = ResumeGenerator()
            resume_data = generator.generate_resume_content(user_data)
            
            if resume_data:
                st.success("Resume Generated Successfully!")
                st.subheader("Preview Summary")
                st.info(resume_data.get('summary', ''))
                
                try:
                    pdf = ResumePDF()
                    pdf.create_resume(resume_data, user_data)
                    pdf_bytes = bytes(pdf.output())
                    
                    st.download_button(
                        label="📥 Download PDF Resume",
                        data=pdf_bytes,
                        file_name=f"resume_{name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"PDF Output Error: {str(e)}")

if __name__ == "__main__":
    main()
