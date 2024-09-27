import os
import openai
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

openai.api_key = os.getenv('OPENAI_API_KEY')

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
        # Placeholder for processing
        return jsonify({'success': True, 'summary': summary})
    else:
        return jsonify({'success': False, 'error': 'Invalid file type'})

if __name__ == '__main__':
    app.run(debug=True)
