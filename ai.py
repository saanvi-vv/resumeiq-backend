from groq import Groq
from dotenv import load_dotenv
import os
import json
import re

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def extract_json_from_response(text: str) -> dict:
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        text = json_match.group(1)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "match_score": 50,
            "missing_keywords": ["Could not parse response"],
            "strong_keywords": [],
            "overall_feedback": text,
            "sections": {},
            "top_suggestions": ["Please try again"]
        }


async def analyze_resume(resume_text: str, job_description: str) -> dict:
    prompt = f"""
    You are an expert ATS (Applicant Tracking System) and resume analyzer.
    
    Analyze the following resume against the job description and provide a detailed analysis.
    
    RESUME:
    {resume_text}
    
    JOB DESCRIPTION:
    {job_description}
    
    Provide your analysis in the following JSON format ONLY. No extra text, just the JSON:
    {{
        "match_score": <integer 0-100 representing how well the resume matches the job>,
        "missing_keywords": [<list of important keywords from JD missing in resume>],
        "strong_keywords": [<list of keywords present in both resume and JD>],
        "overall_feedback": "<2-3 sentences of overall assessment>",
        "sections": {{
            "skills": {{
                "score": <integer 0-100>,
                "feedback": "<specific feedback about skills section>",
                "suggestions": [<list of specific improvements>]
            }},
            "experience": {{
                "score": <integer 0-100>,
                "feedback": "<specific feedback about experience section>",
                "suggestions": [<list of specific improvements>]
            }},
            "education": {{
                "score": <integer 0-100>,
                "feedback": "<specific feedback about education section>",
                "suggestions": [<list of specific improvements>]
            }},
            "overall_presentation": {{
                "score": <integer 0-100>,
                "feedback": "<feedback about formatting and presentation>",
                "suggestions": [<list of specific improvements>]
            }}
        }},
        "top_suggestions": [<list of 5 most important improvements to make>]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
        )
        result_text = response.choices[0].message.content
        return extract_json_from_response(result_text)

    except Exception as e:
        return {
            "match_score": 0,
            "missing_keywords": [],
            "strong_keywords": [],
            "overall_feedback": f"Analysis failed: {str(e)}",
            "sections": {},
            "top_suggestions": ["Please try again"]
        }


def extract_text_from_pdf(file_bytes: bytes) -> str:
    import PyPDF2
    import io

    pdf_file = io.BytesIO(file_bytes)
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"Could not read PDF: {str(e)}")