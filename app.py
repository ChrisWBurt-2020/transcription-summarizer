import os
import openai
import boto3
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')
AWS_REGION = os.getenv('AWS_REGION')
SES_SENDER_EMAIL = os.getenv('SES_SENDER_EMAIL')

ses_client = boto3.client('ses',
                          aws_access_key_id=AWS_ACCESS_KEY,
                          aws_secret_access_key=AWS_SECRET_KEY,
                          region_name=AWS_REGION)

openai.api_key = os.getenv('OPENAI_API_KEY')

def send_email(recipient_email, summary):
    response = ses_client.send_email(
        Source=SES_SENDER_EMAIL,
        Destination={'ToAddresses': [recipient_email]},
        Message={
            'Subject': {'Data': 'Your Summarized Transcription'},
            'Body': {
                'Text': {'Data': summary}
            }
        }
    )

def read_transcription(file_path):
    with open(file_path, 'r') as f:
        return f.read()

def summarize_text(text):
    response = openai.Completion.create(
        engine='text-davinci-003',
        prompt=f"Summarize the following text:\n\n{text}",
        max_tokens=150
    )
    summary = response.choices[0].text.strip()
    return summary

# Configure upload folder and allowed extensions
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'docx'}

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'transcription' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})

    file = request.files['transcription']
    email = request.form.get('email')

    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        transcription_text = read_transcription(file_path)
        summary = summarize_text(transcription_text)
        send_email(email, summary)
        # Placeholder for processing
        return jsonify({'success': True, 'message': 'Summary emailed successfully'})
    
        # return jsonify({'success': True, 'summary': summary})
    else:
        return jsonify({'success': False, 'error': 'Invalid file type'})

if __name__ == '__main__':
    app.run(debug=True)
