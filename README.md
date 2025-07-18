# Spently AI Receipt Analyzer

A modern, privacy-friendly AI-powered receipt analyzer built with Streamlit, SQLite, and Tesseract OCR.

## Features
- 📸 Upload receipt images (JPG, PNG) or PDFs
- 🧾 Automatic OCR extraction of store, date, items, prices, and total
- 🔒 Per-user privacy: each user gets a private data space (no login required)
- 💬 Chat interface: ask questions about your receipts (totals, items, vendors, etc.)
- 📊 Monthly and vendor expense summaries
- 🗑️ Delete receipts
- 📤 Export your data to CSV

## How It Works
- When you open the app, a unique (anonymous) ID is generated for your session.
- All your receipts and items are stored under this ID in the database.
- Only you (in your browser/session) can see and manage your data.

## Requirements
- Python 3.8+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (system dependency)
- [Poppler](https://poppler.freedesktop.org/) (for PDF support)
- Python packages: see `requirements.txt`

## Local Installation
1. **Clone the repo:**
   ```bash
   git clone https://github.com/syedryanahmed/Spently-AI-Receipt-Analyzer.git
   cd Spently-AI-Receipt-Analyzer
   ```
2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Install system dependencies:**
   - On Ubuntu/Debian:
     ```bash
     sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils
     ```
   - On Mac (with Homebrew):
     ```bash
     brew install tesseract poppler
     ```
4. **Run the app:**
   ```bash
   streamlit run app.py
   ```

## Deploy on Streamlit Cloud
1. Push your code to GitHub (including `packages.txt` for system dependencies).
2. Go to [streamlit.io/cloud](https://streamlit.io/cloud) and sign in.
3. Click "New app", select your repo, and set the main file to `app.py`.
4. Deploy! Streamlit Cloud will install everything automatically.

## Usage Tips
- Upload receipts one at a time. Each upload is private to your session.
- Use the chat to ask about totals, items, vendors, or specific receipts (e.g., "What did I buy at Starbucks?", "List all items from my last receipt").
- Export your data to CSV from the sidebar.
- Your data is private to your browser session (unless you clear cookies or use a different device).

---

Built with ❤️ by [syedryanahmed](https://github.com/syedryanahmed) 