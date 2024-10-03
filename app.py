import os
import boto3
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import uuid
from validate_email import validate_email
import re
import PyPDF2
import docx

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# AWS SES and Polly configuration
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
AWS_REGION = os.getenv('AWS_REGION')
SES_SENDER_EMAIL = os.getenv('SES_SENDER_EMAIL')

ses_client = boto3.client(
    'ses',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

polly_client = boto3.client(
    'polly',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

# OpenAI client initialization
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Helper Functions

def extract_section(summary, section_title):
    """
    Extracts the content of a specific section from the summary.
    """
    pattern = rf"{section_title}:\s*(.*?)\n\n"
    match = re.search(pattern, summary, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "N/A"

def format_bullet_points(section_text):
    """
    Formats each line of the section text as a list item.
    """
    # Split the section text into lines and wrap each line in <li> tags
    lines = section_text.split('\n')
    bullet_points = ""
    for line in lines:
        line = line.strip()
        if line:
            bullet_points += f"<li>{line}</li>"
    return bullet_points if bullet_points else "<li>N/A</li>"

def send_email(recipient_emails, summary, audio_path):
    if not recipient_emails or not all(isinstance(email, str) for email in recipient_emails):
        print("Invalid recipient emails")
        return False, "Invalid recipient emails"

    try:
        # Create a multipart/mixed parent container
        msg = MIMEMultipart('mixed')
        msg['Subject'] = 'Your Summarized Transcription'
        msg['From'] = SES_SENDER_EMAIL
        msg['To'] = ", ".join(recipient_emails)  # Combine all emails in the 'To' header

        # Create a multipart/alternative child container
        msg_body = MIMEMultipart('alternative')

        # Define the HTML content with improved formatting
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2E86C1;">Your Meeting Summary</h2>
                <hr>
                <h3>Key Points:</h3>
                <ul>
                    {format_bullet_points(extract_section(summary, "Key Points"))}
                </ul>
                <h3>Action Items:</h3>
                <ul>
                    {format_bullet_points(extract_section(summary, "Action Items"))}
                </ul>
                <h3>Decisions Made:</h3>
                <ul>
                    {format_bullet_points(extract_section(summary, "Decisions Made"))}
                </ul>
                <h3>Recommendations:</h3>
                <ul>
                    {format_bullet_points(extract_section(summary, "Recommendations"))}
                </ul>
                <hr>
                <p>If you have any questions or need further assistance, feel free to reach out.</p>
                <p>Best regards,<br>Recap.AI Team</p>
            </body>
        </html>
        """

        # Define a plain text version for email clients that do not support HTML
        text_content = f"""
        Your Meeting Summary

        Key Points:
        {extract_section(summary, "Key Points")}

        Action Items:
        {extract_section(summary, "Action Items")}

        Decisions Made:
        {extract_section(summary, "Decisions Made")}

        Recommendations:
        {extract_section(summary, "Recommendations")}

        If you have any questions or need further assistance, feel free to reach out.

        Best regards,
        Recap.AI Team
        """

        # Encode the text and HTML content
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')

        # Attach parts into msg_body
        msg_body.attach(text_part)
        msg_body.attach(html_part)

        # Attach the msg_body to the parent container
        msg.attach(msg_body)

        # Attach the audio file
        if audio_path and os.path.exists(audio_path):
            with open(audio_path, 'rb') as attachment:
                part = MIMEBase('audio', 'mp3')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename=summary.mp3',
            )
            msg.attach(part)

        # Send the email via SES
        response = ses_client.send_raw_email(
            Source=SES_SENDER_EMAIL,
            Destinations=recipient_emails,  # List of recipient emails
            RawMessage={
                'Data': msg.as_string(),
            }
        )
        return True, "Email sent successfully"
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False, str(e)

def text_to_speech(text, filename=None):
    try:
        if not filename:
            filename = f"summary_{uuid.uuid4().hex}.mp3"
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId='Joanna'  # You can choose different voices
        )

        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Save the audio stream to a file
        with open(audio_path, 'wb') as file:
            file.write(response['AudioStream'].read())

        return audio_path
    except Exception as e:
        print(f"Error converting text to speech: {str(e)}")
        return None

def read_transcription(file_path):
    # Handle different file types appropriately
    _, file_extension = os.path.splitext(file_path)
    if file_extension.lower() == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    elif file_extension.lower() == '.pdf':
        # Implement PDF reading logic
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
    elif file_extension.lower() == '.docx':
        # Implement DOCX reading logic
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    else:
        return ""

def summarize_text(text):
    prompt = (
        "Please provide a comprehensive and structured summary of the following meeting transcription. "
        "The summary should be business-oriented and include the following sections:\n\n"
        "1. **Key Points:** A bullet-point list of the main topics discussed.\n"
        "2. **Action Items:** Specific tasks assigned, including who is responsible and deadlines if mentioned.\n"
        "3. **Decisions Made:** Any decisions or agreements reached during the meeting.\n"
        "4. **Recommendations:** Suggestions or recommendations proposed.\n\n"
        "Ensure the summary is clear, concise, and well-organized."
    )
    
    try:
        # Send request to OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\n\n{text}",
                }
            ]
        )

        # Debugging: Print the response structure
        print(response)  # You can check the actual response structure in your console.

        # Adjusting how we extract the summary based on expected structure
        try:
            summary = response.choices[0].message.content.strip()
            return summary
        except AttributeError:
            return "There was an error processing the response from OpenAI."
    except Exception as e:
        print(f"Error summarizing text: {str(e)}")
        return "There was an error summarizing the transcription."

# Configure upload folder and allowed extensions
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'docx'}

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'transcription' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400

    file = request.files['transcription']
    emails = request.form.get('emails')

    # Debugging: Log the received emails
    app.logger.debug(f"Received emails: {emails}")
    print(f"Received emails: {emails}")  # Alternatively, use print for quick debugging

    if not emails:
        return jsonify({'success': False, 'error': 'Emails are required'}), 400

    # Split the emails by comma and strip any whitespace
    email_list = [email.strip() for email in emails.split(',') if email.strip()]

    # Validate each email address
    invalid_emails = [email for email in email_list if not validate_email(email)]

    if invalid_emails:
        return jsonify({
            'success': False,
            'error': f'Invalid email address(es): {", ".join(invalid_emails)}'
        }), 400

    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        transcription_text = read_transcription(file_path)
        summary = summarize_text(transcription_text)
        
        # Convert summary to speech
        audio_path = text_to_speech(summary)
        
        # Send email with summary and audio to all recipients
        email_sent, message = send_email(email_list, summary, audio_path)
        
        # Optionally, clean up the audio file after sending
        if audio_path:
            try:
                os.remove(audio_path)
            except OSError as e:
                app.logger.error(f"Error deleting audio file: {str(e)}")

        return jsonify({'success': email_sent, 'message': message})
    else:
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400

if __name__ == '__main__':
    app.run(debug=True)
