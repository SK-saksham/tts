# Document to Speech

A simple web application that converts PDF, DOCX, and TXT files into speech (MP3) using Microsoft Edge's neural voices (`edge-tts`). 

## Features
- Upload PDF, Word (.docx), or Text (.txt) files.
- Choose from multiple high-quality Neural voices (English, Hindi, Marathi, etc.).
- Adjust speech rate (slow, normal, fast, very fast).
- Download the generated audio as an MP3 file.

## Prerequisites
- Python 3.8+ 
- Internet connection (required for `edge-tts` to fetch the audio)

## Installation & Local Setup

1. **Clone or download this repository**
2. **Create a virtual environment (optional but recommended)**:
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```
3. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the App

### Development Mode
To run the Flask development server:
```bash
python app.py
```
Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

### Production Mode (Windows)
For a production environment on Windows, you can use `waitress`:
```bash
waitress-serve --host=127.0.0.1 --port=5000 app:app
```

### Production Mode (Linux / macOS)
For a production environment on Unix-based systems, use `gunicorn`:
```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
```

## Running with Docker

You can also run the application using Docker:

1. **Build the image**:
   ```bash
   docker build -t doc2speech .
   ```
2. **Run the container**:
   ```bash
   docker run -d -p 5000:5000 doc2speech
   ```
3. Access the app at [http://localhost:5000](http://localhost:5000).

## Note
- The application stores temporary audio files in your system's temp directory.
- Large files may take a few minutes to process depending on your internet connection.

## Deploying to Render

This project is fully configured to be deployed on [Render](https://render.com/).

### 1-Click Deployment (Blueprint)
Since a `render.yaml` file is included, you can use Render's Blueprint feature:
1. Push this repository to GitHub, GitLab, or Bitbucket.
2. Log in to your Render Dashboard.
3. Go to **Blueprints** and click **New Blueprint Instance**.
4. Connect your repository. Render will automatically detect the `render.yaml` configuration and deploy the app.

### Manual Web Service Deployment
1. On the Render Dashboard, click **New +** and select **Web Service**.
2. Connect your repository.
3. Set the following values (if not automatically populated):
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. Click **Create Web Service**.

> **Note on Storage:** Render's free tier provides an ephemeral filesystem, which is perfectly fine for this app since the generated MP3 files are saved to temporary storage and meant to be downloaded immediately.
