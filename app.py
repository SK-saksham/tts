"""
Document to Speech
Upload a PDF or Word (.docx) file and download the whole thing as an MP3.

Run:  python app.py   then open http://127.0.0.1:5000
Needs an internet connection (uses Microsoft Edge's neural voices via edge-tts).
"""
import asyncio
import io
import re
import tempfile
import uuid
from pathlib import Path

import edge_tts
from docx import Document
from flask import Flask, jsonify, render_template_string, request, send_file
from pypdf import PdfReader

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

OUT_DIR = Path(__file__).parent / "output"
OUT_DIR.mkdir(exist_ok=True)

VOICES = {
    "en-IN-NeerjaNeural": "English (India) - Neerja, female",
    "en-IN-PrabhatNeural": "English (India) - Prabhat, male",
    "hi-IN-SwaraNeural": "Hindi - Swara, female",
    "hi-IN-MadhurNeural": "Hindi - Madhur, male",
    "mr-IN-AarohiNeural": "Marathi - Aarohi, female",
    "mr-IN-ManoharNeural": "Marathi - Manohar, male",
    "en-US-AriaNeural": "English (US) - Aria, female",
    "en-US-GuyNeural": "English (US) - Guy, male",
    "en-GB-SoniaNeural": "English (UK) - Sonia, female",
}

CHUNK_CHARS = 2500


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
        return "\n\n".join(pages)
    if ext == ".docx":
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(", ".join(cells))
        return "\n\n".join(parts)
    if ext == ".txt":
        return data.decode("utf-8", errors="ignore")
    raise ValueError("Unsupported file type. Please upload a PDF, DOCX or TXT file.")


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")              # soft hyphens
    text = re.sub(r"-\n(?=[a-z])", "", text)       # join words hyphenated at line end
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)   # single newlines -> space
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chunks(text: str, limit: int = CHUNK_CHARS):
    sentences = re.split(r"(?<=[.!?।])\s+|\n\n", text)
    chunk = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        while len(s) > limit:  # very long sentence: hard split
            cut = s.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if chunk:
                yield chunk
                chunk = ""
            yield s[:cut]
            s = s[cut:].strip()
        if len(chunk) + len(s) + 1 > limit:
            if chunk:
                yield chunk
            chunk = s
        else:
            chunk = f"{chunk} {s}".strip()
    if chunk:
        yield chunk


async def synthesize_chunk(chunk: str, voice: str, rate: str) -> bytes:
    comm = edge_tts.Communicate(chunk, voice, rate=rate)
    audio_data = bytearray()
    async for msg in comm.stream():
        if msg["type"] == "audio":
            audio_data.extend(msg["data"])
    return bytes(audio_data)


async def synthesize(text: str, voice: str, rate: str, out_path: Path):
    chunks = list(split_chunks(text))
    sem = asyncio.Semaphore(10)  # limit concurrency to avoid rate limits
    
    async def process_with_sem(chunk):
        async with sem:
            return await synthesize_chunk(chunk, voice, rate)
            
    tasks = [process_with_sem(chunk) for chunk in chunks]
    results = await asyncio.gather(*tasks)
    
    with open(out_path, "wb") as f:
        for audio_bytes in results:
            f.write(audio_bytes)


PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Document to Speech</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #f3f4f6;
    --card: #ffffff;
    --ink: #111827;
    --muted: #6b7280;
    --accent: #4f46e5;
    --accent-hover: #4338ca;
    --line: #e5e7eb;
    --ring: rgba(79, 70, 229, 0.2);
    --radius: 16px;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #111827;
      --card: #1f2937;
      --ink: #f9fafb;
      --muted: #9ca3af;
      --accent: #6366f1;
      --accent-hover: #818cf8;
      --line: #374151;
      --ring: rgba(99, 102, 241, 0.2);
    }
  }
  * { box-sizing: border-box; }
  body { 
    margin: 0; 
    font-family: 'Inter', system-ui, -apple-system, sans-serif; 
    background: var(--bg); 
    color: var(--ink); 
    display: flex;
    min-height: 100vh;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  main { width: 100%; max-width: 600px; margin: auto; }
  .card { 
    background: var(--card); 
    border: 1px solid var(--line); 
    border-radius: var(--radius); 
    padding: 36px; 
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  }
  h1 { font-size: 26px; font-weight: 700; margin: 0 0 8px; letter-spacing: -0.025em; }
  p.sub { color: var(--muted); margin: 0 0 28px; font-size: 15px; line-height: 1.5; }
  
  .form-group { margin-bottom: 20px; }
  label { display: block; font-size: 14px; font-weight: 600; margin-bottom: 8px; color: var(--ink); }
  
  select, input[type=file], textarea { 
    width: 100%; 
    padding: 12px 16px; 
    border: 1px solid var(--line); 
    border-radius: 10px; 
    background: var(--bg); 
    color: var(--ink); 
    font-size: 15px; 
    transition: all 0.2s;
    font-family: inherit;
  }
  select:focus, input[type=file]:focus, textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 4px var(--ring);
  }
  
  input[type=file]::file-selector-button {
    background: var(--line);
    border: 0;
    padding: 8px 14px;
    border-radius: 8px;
    color: var(--ink);
    font-weight: 600;
    margin-right: 14px;
    cursor: pointer;
    transition: background 0.2s;
  }
  input[type=file]::file-selector-button:hover {
    background: var(--muted);
    color: #fff;
  }
  
  button[type="submit"] { 
    margin-top: 12px; 
    width: 100%; 
    padding: 16px; 
    border: 0; 
    border-radius: 10px; 
    background: var(--accent); 
    color: #fff; 
    font-size: 16px; 
    font-weight: 600; 
    cursor: pointer; 
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }
  button[type="submit"]:hover:not(:disabled) { background: var(--accent-hover); transform: translateY(-1px); }
  button[type="submit"]:active:not(:disabled) { transform: translateY(1px); }
  button:disabled { opacity: 0.7; cursor: wait; transform: none; }
  
  #status { 
    margin-top: 24px; 
    font-size: 14.5px; 
    color: var(--muted); 
    text-align: center;
    font-weight: 500;
    min-height: 20px;
  }
  .err { color: #ef4444 !important; }
  
  #result { 
    margin-top: 24px; 
    display: none; 
    padding-top: 28px;
    border-top: 1px solid var(--line);
  }
  
  audio { width: 100%; height: 50px; outline: none; border-radius: 25px; }
  
  .controls-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 20px;
    gap: 16px;
    flex-wrap: wrap;
  }
  
  .speed-control {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--bg);
    padding: 10px 18px;
    border-radius: 20px;
    border: 1px solid var(--line);
  }
  .speed-control label { margin: 0; font-size: 13px; font-weight: 600; color: var(--muted); }
  .speed-control input[type=range] { width: 100px; accent-color: var(--accent); cursor: pointer; }
  .speed-control span { font-variant-numeric: tabular-nums; font-weight: 700; width: 32px; text-align: right; font-size: 14px; color: var(--accent);}
  
  .download-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 12px 24px;
    background: var(--bg);
    border: 1px solid var(--line);
    color: var(--ink);
    text-decoration: none;
    font-weight: 600;
    font-size: 14px;
    border-radius: 24px;
    transition: all 0.2s;
  }
  .download-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--card);
  }
  
  .download-btn svg { width: 18px; height: 18px; margin-right: 8px; }
  
  .text-box-container { margin-top: 28px; }
  .text-box-container label { font-size: 14px; font-weight: 600; color: var(--muted); margin-bottom: 10px; display: block; }
  .text-container { 
    height: 260px; 
    line-height: 1.7; 
    overflow-y: auto; 
    padding: 20px; 
    border: 1px solid var(--line); 
    border-radius: 12px; 
    background: var(--bg); 
    color: var(--muted); 
    font-size: 15px; 
    font-family: inherit;
  }
  .highlighted-text {
    color: var(--accent);
    font-weight: 600;
    background: var(--ring);
    border-radius: 4px;
    padding: 2px 0;
  }
  
  .spinner {
    display: none;
    width: 20px;
    height: 20px;
    border: 3px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 1s ease-in-out infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<main>
  <div class="card">
    <h1>Document to Speech</h1>
    <p class="sub">Upload a PDF or Word file and convert it into high-quality audio.</p>
    
    <form id="f">
      <div class="form-group">
        <label>Document (.pdf, .docx, .txt)</label>
        <input type="file" name="file" accept=".pdf,.docx,.txt" required>
      </div>
      
      <div class="form-group">
        <label>AI Voice</label>
        <select name="voice">
          {% for k, v in voices.items() %}<option value="{{k}}">{{v}}</option>{% endfor %}
        </select>
      </div>
      
      <div class="form-group">
        <label>Reading Speed</label>
        <select name="rate">
          <option value="-20%">Slow</option>
          <option value="+0%" selected>Normal</option>
          <option value="+15%">Fast</option>
          <option value="+30%">Very fast</option>
        </select>
      </div>
      
      <button id="go" type="submit">
        <div class="spinner" id="spinner"></div>
        <span id="btnText">Convert to Audio</span>
      </button>
    </form>
    
    <div id="status"></div>
    
    <div id="result">
      <audio id="player" controls></audio>
      
      <div class="controls-row">
        <div class="speed-control">
          <label for="playbackSpeed">Playback Speed</label>
          <input type="range" id="playbackSpeed" min="0.5" max="2" step="0.1" value="1" 
                 oninput="document.getElementById('player').playbackRate = this.value; document.getElementById('speedLabel').innerText = Number(this.value).toFixed(1) + 'x';">
          <span id="speedLabel">1.0x</span>
        </div>
        
        <a id="dl" class="download-btn" download="audio.mp3">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          Download MP3
        </a>
      </div>
      
      <div class="text-box-container">
        <label>Document Text (What's being read)</label>
        <div id="extractedText" class="text-container"></div>
      </div>
    </div>
  </div>
</main>

<script>
const f = document.getElementById('f'), st = document.getElementById('status'),
      go = document.getElementById('go'), res = document.getElementById('result'),
      spinner = document.getElementById('spinner'), btnText = document.getElementById('btnText');

f.addEventListener('submit', async e => {
  e.preventDefault();
  res.style.display = 'none'; 
  st.className = '';
  st.textContent = 'Reading the document and generating audio...';
  go.disabled = true;
  spinner.style.display = 'block';
  btnText.textContent = 'Processing...';
  
  try {
    const r = await fetch('/convert', { method:'POST', body:new FormData(f) });
    let j;
    const text_res = await r.text();
    try {
      j = JSON.parse(text_res);
    } catch (parseErr) {
      if (!r.ok) throw new Error(`Server error (${r.status}). The file might be too large and timed out.`);
      throw new Error('Invalid response from server.');
    }
    if (!r.ok) throw new Error(j.error || 'Something went wrong');
    
    document.getElementById('player').src = j.url;
    const dl = document.getElementById('dl');
    dl.href = j.url + '?dl=1'; 
    dl.download = j.name;
    
    const player = document.getElementById('player');
    const extText = document.getElementById('extractedText');
    
    document.getElementById('playbackSpeed').value = 1;
    document.getElementById('speedLabel').innerText = '1.0x';
    extText.innerHTML = "Loading text...";
    res.style.display = 'block';
    
    // Teleprompter Logic
    window.lineData = [];
    window.activeLine = null;
    
    if (j.text_url) {
      try {
        const textRes = await fetch(j.text_url);
        if (textRes.ok) {
          const text = await textRes.text();
          extText.innerHTML = '';
          const segments = text.match(/[^.!?\\n]+[.!?\\n]*\\s*/g) || [text];
          let cumulative = 0;
          let totalChars = text.length;
          
          segments.forEach((seg, i) => {
            const span = document.createElement('span');
            span.textContent = seg;
            span.style.transition = 'color 0.2s, background 0.2s';
            extText.appendChild(span);
            
            let startRatio = cumulative / totalChars;
            cumulative += seg.length;
            let endRatio = cumulative / totalChars;
            window.lineData.push({ el: span, start: startRatio, end: endRatio });
          });
        } else {
          extText.innerHTML = "Could not load text.";
        }
      } catch (e) {
        extText.innerHTML = "Error loading text.";
      }
    }
    
    player.ontimeupdate = () => {
      if (!player.duration || window.lineData.length === 0) return;
      const progress = player.currentTime / player.duration;
      let currentLine = window.lineData.find(ld => progress >= ld.start && progress <= ld.end);
      if (!currentLine) currentLine = window.lineData[window.lineData.length - 1];
      
      if (currentLine !== window.activeLine) {
        if (window.activeLine) window.activeLine.el.className = '';
        currentLine.el.className = 'highlighted-text';
        window.activeLine = currentLine;
        
        // Scroll to center
        const containerHeight = extText.clientHeight;
        const lineTop = currentLine.el.offsetTop - extText.offsetTop;
        extText.scrollTo({
          top: lineTop - (containerHeight / 2) + 20,
          behavior: 'smooth'
        });
      }
    };
    
    st.textContent = `Success! ${j.chars.toLocaleString()} characters converted.`;
  } catch (err) {
    st.className = 'err'; st.textContent = err.message;
  } finally { 
    go.disabled = false; 
    spinner.style.display = 'none';
    btnText.textContent = 'Convert to Audio';
  }
});
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE, voices=VOICES)


@app.post("/convert")
def convert():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(error="Please choose a file."), 400
    voice = request.form.get("voice", "en-IN-NeerjaNeural")
    rate = request.form.get("rate", "+0%")
    if voice not in VOICES:
        return jsonify(error="Unknown voice."), 400
    try:
        text = clean_text(extract_text(file.filename, file.read()))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception:
        return jsonify(error="Could not read that file. Is it corrupted or password protected?"), 400
    if not text:
        return jsonify(error="No readable text found. Scanned PDFs (images) need OCR first."), 400

    OUT_DIR.mkdir(exist_ok=True)
    out_id = uuid.uuid4().hex
    out_path = OUT_DIR / f"{out_id}.mp3"
    try:
        asyncio.run(synthesize(text, voice, rate, out_path))
    except Exception as e:
        return jsonify(error=f"Speech generation failed (check your internet connection): {e}"), 500

    name = Path(file.filename).stem + ".mp3"
    (OUT_DIR / f"{out_id}.name").write_text(name, encoding="utf-8")
    (OUT_DIR / f"{out_id}.txt").write_text(text, encoding="utf-8")
    return jsonify(url=f"/audio/{out_id}", text_url=f"/text/{out_id}", name=name, chars=len(text))


@app.get("/audio/<out_id>")
def audio(out_id):
    if not re.fullmatch(r"[0-9a-f]{32}", out_id):
        return "Not found", 404
    path = OUT_DIR / f"{out_id}.mp3"
    if not path.exists():
        return "Not found", 404
    name_file = OUT_DIR / f"{out_id}.name"
    name = name_file.read_text(encoding="utf-8") if name_file.exists() else "audio.mp3"
    return send_file(path, mimetype="audio/mpeg",
                     as_attachment=bool(request.args.get("dl")), download_name=name)


@app.get("/text/<out_id>")
def text_endpoint(out_id):
    if not re.fullmatch(r"[0-9a-f]{32}", out_id):
        return "Not found", 404
    path = OUT_DIR / f"{out_id}.txt"
    if not path.exists():
        return "Not found", 404
    return send_file(path, mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
