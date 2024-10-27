# youtube_summarizer.py
import http.client
from youtube_transcript_api import YouTubeTranscriptApi
from transformers import pipeline
from fpdf import FPDF
import pyttsx3
import torch
from concurrent.futures import ThreadPoolExecutor

# Initialize text-to-speech engine
tts_engine = pyttsx3.init()

# Initialize summarizer with specific model and device
device = "cuda" if torch.cuda.is_available() else "cpu"
summarizer = pipeline(
    "summarization",
    model="facebook/bart-large-cnn",  # Using a faster model
    device=device  # Use GPU if available
)

# Function to extract video ID from link
def extract_video_id(link):
    try:
        if not link or "v=" not in link:
            return None
        video_id = link.split("v=")[1].split("&")[0]  # Handle additional parameters
        return video_id if video_id else None
    except Exception as e:
        print(f"Error extracting video ID: {str(e)}")
        return None

# Function to chunk text into smaller pieces
def chunk_text(text, max_length=1024):
    # Optimize chunking for better summary quality
    sentences = text.split('. ')
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        words = sentence.split()
        if current_length + len(words) <= max_length:
            current_chunk.append(sentence)
            current_length += len(words)
        else:
            yield '. '.join(current_chunk) + '.'
            current_chunk = [sentence]
            current_length = len(words)
    
    if current_chunk:
        yield '. '.join(current_chunk) + '.'

# Function to summarize chunk
def summarize_chunk(chunk):
    try:
        return summarizer(
            chunk,
            max_length=150,
            min_length=50,
            do_sample=False,
            truncation=True
        )[0]['summary_text']
    except Exception as e:
        print(f"Error summarizing chunk: {str(e)}")
        return ""

# Function to summarize video transcript
def summarize_transcript(transcript_text):
    # Optimize chunk size and parallel processing
    chunks = list(chunk_text(transcript_text, max_length=500))
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=min(len(chunks), 4)) as executor:
        summaries = list(executor.map(summarize_chunk, chunks))
    
    # Join summaries intelligently
    final_summary = ' '.join(summary for summary in summaries if summary)
    return final_summary

# Function to generate PDF
def generate_pdf(summary_text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="YouTube Video Summary", ln=True, align="C")
    
    # Handle UTF-8 characters
    try:
        pdf.multi_cell(0, 10, summary_text.encode('latin-1', 'replace').decode('latin-1'))
    except Exception:
        pdf.multi_cell(0, 10, summary_text.encode('latin-1', 'ignore').decode('latin-1'))
    
    pdf_file = "summary.pdf"
    pdf.output(pdf_file)
    return pdf_file

# Function to speak text
def speak_text(text):
    tts_engine.setProperty('rate', 150)
    tts_engine.setProperty('voice', tts_engine.getProperty('voices')[0].id)  # Set default voice
    
    # Split text into smaller chunks for smoother speech
    sentences = text.split('.')
    for sentence in sentences:
        if sentence.strip():
            tts_engine.say(sentence.strip())
            tts_engine.runAndWait()

# Cache for storing recent summaries
summary_cache = {}

def get_video_summary(video_id):
    # Check cache first
    if video_id in summary_cache:
        return summary_cache[video_id]
    
    try:
        # Get video transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = ' '.join([t['text'] for t in transcript])
        
        # Generate summary
        summary = summarize_transcript(transcript_text)
        
        # Cache the result
        summary_cache[video_id] = summary
        
        return summary
    except Exception as e:
        print(f"Error in get_video_summary: {str(e)}")
        return None
