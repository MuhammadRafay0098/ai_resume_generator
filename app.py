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

class ResumeGenerator:
    def __init__(self):
        self.client = init_groq_client()
        self.model = "openai/gpt-oss-20b"
    
    def clean_json_response(self, content):
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        json_match = re.search(r'\{[\s\S]*?\}', content)
        if not json_match:
            return None
        json_str = json_match.group()
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        return json_str
    
    def safe_parse_json(self, json_str):
        try:
            return json.loads(json_str)
        except Exception:
            return self.get_default_resume({})

    def generate_resume_content(self, data):
        prompt = f"""
        Create an ATS-optimized resume in JSON format based on:
        Name: {data.get('name', '')}
        Email: {data.get('email', '')}
        Phone: {data.get('phone', '')}
        LinkedIn: {data.get('linkedin', '')}
        Experience: {data.get('experience', '')}
        Education: {data.get('education', '')}
        Skills: {data.get('skills', '')}
        Projects: {data.get('projects', '')}
        
        Return ONLY a valid JSON object with this exact structure:
        {{
            "summary": "professional summary text",
            "experience": [
                {{"title": "Job Title", "company": "Company Name", "period": "Date Range", "responsibilities": ["achievement 1", "achievement 2"]}}
            ],
            "education": ["Degree | University | Year"],
            "skills": ["Skill 1", "Skill 2"],
            "projects": [
                {{"name": "Project Name", "description": "Brief description", "technologies": ["Tech1"], "achievements": ["Achievement 1"]}}
            ]
        }}
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert resume writer. Return ONLY valid raw JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            clean_json = self.clean_json_response(content)
            if clean_json:
                parsed = self.safe_parse_json(clean_json)
                if parsed:
                    return parsed
            return self.get_default_resume(data)
                
        except Exception as e:
            st.error(f"AI Generation Warning: {str(e)}")
            return self.get_default_resume(data)
    
    def get_default_resume(self, data):
        return {
            "summary": f"Experienced professional skilled in {data.get('skills', 'relevant domain topics')}.",
            "experience": [
                {
                    "title": "Professional Experience",
                    "company": "Various Organizations",
                    "period": "Recent",
                    "responsibilities": ["Delivered results according to expectations.", "Collaborated effectively with team members."]
                }
            ],
            "education": [data.get('education', 'Education Information Provided')],
            "skills": [s.strip() for s in data.get('skills', '').split(',') if s.strip()] or ["Core Skills"],
            "projects": []
        }

class ResumePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)
    
    def clean_text(self, text):
        if not text:
            return ""
        return str(text).encode('latin-1', 'replace').decode('latin-1').strip()
    
    def create_resume(self, content, user_data):
        self.add_page()
        
        # Name
        self.set_font('Helvetica', 'B', 22)
        self.set_text_color(30, 60, 90)
        self.cell(0, 12, self.clean_text(user_data.get('name', '')), 0, 1, 'C')
        
        # Contact
        self.set_font('Helvetica', '', 10)
        self.set_text_color(80, 80, 80)
        contact = []
        if user_data.get('email'): contact.append(f"Email: {user_data['email']}")
        if user_data.get('phone'): contact.append(f"Phone: {user_data['phone']}")
        if user_data.get('linkedin'): contact.append(f"LinkedIn: {user_data['linkedin']}")
        if contact:
            self.cell(0, 6, self.clean_text(' | '.join(contact)), 0, 1, 'C')
        self.ln(6)
        
        # Summary
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(30, 60, 90)
        self.cell(0, 8, "PROFESSIONAL SUMMARY", 0, 1)
        self.set_draw_color(52, 152, 219)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(3)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, self.clean_text(content.get('summary', '')))
        self.ln(4)
        
        # Experience
        if content.get('experience'):
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(30, 60, 90)
            self.cell(0, 8, "WORK EXPERIENCE", 0, 1)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(3)
            for exp in content['experience']:
                self.set_font('Helvetica', 'B', 11)
                self.set_text_color(0, 0, 0)
                title = self.clean_text(exp.get('title', ''))
                company = self.clean_text(exp.get('company', ''))
                self.cell(0, 6, f"{title} - {company}" if company else title, 0, 1)
                
                if exp.get('period'):
                    self.set_font('Helvetica', 'I', 9)
                    self.set_text_color(100, 100, 100)
                    self.cell(0, 5, self.clean_text(exp['period']), 0, 1)
                
                self.set_font('Helvetica', '', 10)
                self.set_text_color(0, 0, 0)
                for resp in exp.get('responsibilities', []):
                    self.multi_cell(0, 5, f"- {self.clean_text(resp)}")
                self.ln(2)
        
        # Education
        if content.get('education'):
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(30, 60, 90)
            self.cell(0, 8, "EDUCATION", 0, 1)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(3)
            self.set_font('Helvetica', '', 10)
            self.set_text_color(0, 0, 0)
            for edu in content['education']:
                self.multi_cell(0, 5, f"- {self.clean_text(edu)}")
            self.ln(2)
            
        # Skills
        if content.get('skills'):
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(30, 60, 90)
            self.cell(0, 8, "SKILLS", 0, 1)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(3)
            self.set_font('Helvetica', '', 10)
            self.set_text_color(0, 0, 0)
            skills_text = ', '.join([self.clean_text(s) for s in content['skills']])
            self.multi_cell(0, 5, skills_text)

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