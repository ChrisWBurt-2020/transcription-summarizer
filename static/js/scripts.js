document.getElementById('upload-form').addEventListener('submit', function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = 'Processing...';

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            messageDiv.textContent = 'Summarization complete! Check your email.';
        } else {
            messageDiv.textContent = 'Error: ' + data.error;
        }
    })
    .catch(error => {
        messageDiv.textContent = 'Error: ' + error.message;
    });
});
