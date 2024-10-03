document.getElementById('upload-form').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const messageDiv = document.getElementById('message');
    const emails = document.getElementById('emails').value.split(',').map(email => email.trim()); // Splitting emails by commas
    messageDiv.textContent = 'Processing...';

    // Add emails to FormData
    formData.append('emails', JSON.stringify(emails)); // Convert email array to JSON string

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            messageDiv.textContent = 'Summarization complete! Emails have been sent.';
        } else {
            messageDiv.textContent = 'Error: ' + data.error;
        }
    })
    .catch(error => {
        messageDiv.textContent = 'Error: ' + error.message;
    });
});
