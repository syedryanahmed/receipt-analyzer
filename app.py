import streamlit as st
import sqlite3
import pytesseract
from PIL import Image
import io
import re
import os
import tempfile
import pandas as pd
from datetime import datetime
import uuid

DB_PATH = 'receipts.db'

# --- User UUID Setup ---
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = str(uuid.uuid4())
USER_ID = st.session_state['user_id']

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Check if user_id column exists in receipts
    c.execute("PRAGMA table_info(receipts)")
    columns = [col[1] for col in c.fetchall()]
    if 'user_id' not in columns:
        c.execute("DROP TABLE IF EXISTS receipts")
        c.execute("DROP TABLE IF EXISTS items")
    # Now create tables with user_id
    c.execute('''CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        store TEXT,
        date TEXT,
        total REAL,
        image BLOB
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        receipt_id INTEGER,
        name TEXT,
        price REAL,
        FOREIGN KEY(receipt_id) REFERENCES receipts(id)
    )''')
    conn.commit()
    conn.close()

init_db()

# --- OCR and Parsing ---
def extract_text_from_file(uploaded_file):
    try:
        if uploaded_file.type in ["image/jpeg", "image/png"]:
            image = Image.open(uploaded_file)
            text = pytesseract.image_to_string(image)
            return text
        elif uploaded_file.type == "application/pdf":
            try:
                from pdf2image import convert_from_bytes
            except ImportError:
                st.error("Please install pdf2image: pip install pdf2image")
                return ""
            images = convert_from_bytes(uploaded_file.read())
            text = "\n".join([pytesseract.image_to_string(img) for img in images])
            return text
        else:
            return ""
    except Exception as e:
        st.error(f"OCR extraction failed: {e}")
        return ""

def parse_receipt_text(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    store = "Unknown"
    date = None
    total = None
    items = []
    for l in lines:
        if not re.search(r'\d{2,4}[\-/]\d{1,2}[\-/]\d{1,4}', l) and not re.search(r'(total|amount due|amount)', l, re.IGNORECASE):
            store = l
            break
    date_regex = r'(\d{2,4}[\-/]\d{1,2}[\-/]\d{1,4})'
    for l in lines:
        m = re.search(date_regex, l)
        if m:
            date = m.group(1)
            break
    total_regex = r'(total|amount due|amount)\s*[:\-]?\s*\$?([\d,.]+)'
    for l in reversed(lines):
        m = re.search(total_regex, l, re.IGNORECASE)
        if m:
            try:
                total = float(m.group(2).replace(',', ''))
            except:
                total = None
            break
    price_regex = r'([A-Za-z0-9\s\-]+?)\s+\$?([\d]+\.[\d]{2})'
    for l in lines:
        if re.search(r'(total|amount due|amount)', l, re.IGNORECASE):
            continue
        m = re.match(price_regex, l)
        if m:
            name = m.group(1).strip()
            try:
                price = float(m.group(2))
            except:
                price = None
            if name and price is not None:
                items.append({'name': name, 'price': price})
    if not date:
        for l in lines:
            try:
                dt = datetime.strptime(l, '%Y-%m-%d')
                date = l
                break
            except:
                continue
    if not total:
        for l in reversed(lines):
            m = re.search(r'\$([\d,.]+)', l)
            if m:
                try:
                    total = float(m.group(1).replace(',', ''))
                except:
                    total = None
                break
    return store, date, total, items

# --- Database Operations ---
def insert_receipt(store, date, total, image_bytes, items):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO receipts (user_id, store, date, total, image) VALUES (?, ?, ?, ?, ?)',
              (USER_ID, store, date, total, image_bytes))
    receipt_id = c.lastrowid
    for item in items:
        c.execute('INSERT INTO items (user_id, receipt_id, name, price) VALUES (?, ?, ?, ?)',
                  (USER_ID, receipt_id, item['name'], item['price']))
    conn.commit()
    conn.close()

def get_receipts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, store, date, total FROM receipts WHERE user_id=? ORDER BY date DESC', (USER_ID,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_items_for_receipt(receipt_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT name, price FROM items WHERE user_id=? AND receipt_id=?', (USER_ID, receipt_id))
    items = c.fetchall()
    conn.close()
    return items

def delete_receipt(receipt_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM items WHERE user_id=? AND receipt_id=?', (USER_ID, receipt_id))
    c.execute('DELETE FROM receipts WHERE user_id=? AND id=?', (USER_ID, receipt_id))
    conn.commit()
    conn.close()

def export_receipts_to_csv():
    conn = sqlite3.connect(DB_PATH)
    df_receipts = pd.read_sql_query('SELECT * FROM receipts WHERE user_id=?', conn, params=(USER_ID,))
    df_items = pd.read_sql_query('SELECT * FROM items WHERE user_id=?', conn, params=(USER_ID,))
    conn.close()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        df_receipts.to_csv(tmp.name, index=False)
        df_items.to_csv(tmp.name.replace('.csv', '_items.csv'), index=False)
        return tmp.name, tmp.name.replace('.csv', '_items.csv')

# --- Improved Rule-based Chat Logic ---
def answer_query(query):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    q = query.lower()
    now = datetime.now()
    answer = None
    # Monthly total
    if 'this month' in q or 'current month' in q:
        month = now.strftime('%Y-%m')
        c.execute("SELECT SUM(total) FROM receipts WHERE user_id=? AND date LIKE ?", (USER_ID, f'{month}%'))
        total = c.fetchone()[0]
        answer = f"Total spent this month: ${total:.2f}" if total else "No receipts for this month."
    # Vendor-specific
    elif 'from' in q or 'at' in q:
        for word in ['from', 'at']:
            if word in q:
                vendor = q.split(word)[-1].strip().split()[0]
                c.execute("SELECT date, total, id FROM receipts WHERE user_id=? AND store LIKE ?", (USER_ID, f'%{vendor}%'))
                rows = c.fetchall()
                if rows:
                    total = sum([r[1] for r in rows if r[1]])
                    answer = f"Total spent at {vendor.title()}: ${total:.2f}\n" + "\n".join([f"{r[0]}: ${r[1]:.2f}" for r in rows])
                    # List items for this vendor
                    item_lines = []
                    for r in rows:
                        c.execute("SELECT name, price FROM items WHERE user_id=? AND receipt_id=?", (USER_ID, r[2]))
                        items = c.fetchall()
                        if items:
                            item_lines.append(f"Items for {r[0]}: " + ", ".join([f"{i[0]} (${i[1]:.2f})" for i in items]))
                    if item_lines:
                        answer += "\n" + "\n".join(item_lines)
                else:
                    answer = f"No receipts found for {vendor.title()}."
                break
            else:
                answer = "No matching vendor found."
    # List all items from last receipt
    elif 'last receipt' in q or 'latest receipt' in q:
        c.execute("SELECT id, store, date FROM receipts WHERE user_id=? ORDER BY date DESC LIMIT 1", (USER_ID,))
        row = c.fetchone()
        if row:
            c.execute("SELECT name, price FROM items WHERE user_id=? AND receipt_id=?", (USER_ID, row[0]))
            items = c.fetchall()
            if items:
                answer = f"Items from your last receipt ({row[2]} - {row[1]}):\n" + "\n".join([f"{i[0]}: ${i[1]:.2f}" for i in items])
            else:
                answer = "No items found for your last receipt."
        else:
            answer = "No receipts found."
    # What did I buy at [vendor]?
    elif 'what did i buy at' in q:
        vendor = q.split('what did i buy at')[-1].strip().split()[0]
        c.execute("SELECT id, date FROM receipts WHERE user_id=? AND store LIKE ? ORDER BY date DESC", (USER_ID, f'%{vendor}%'))
        rows = c.fetchall()
        if rows:
            all_items = []
            for r in rows:
                c.execute("SELECT name, price FROM items WHERE user_id=? AND receipt_id=?", (USER_ID, r[0]))
                items = c.fetchall()
                if items:
                    all_items.extend([f"{i[0]} (${i[1]:.2f}) on {r[1]}" for i in items])
            if all_items:
                answer = f"Items bought at {vendor.title()}:\n" + "\n".join(all_items)
            else:
                answer = f"No items found for {vendor.title()}."
        else:
            answer = f"No receipts found for {vendor.title()}."
    # How much did I spend on [item]?
    elif 'how much did i spend on' in q:
        item = q.split('how much did i spend on')[-1].strip().split()[0]
        c.execute("SELECT SUM(price) FROM items WHERE user_id=? AND name LIKE ?", (USER_ID, f'%{item}%'))
        total = c.fetchone()[0]
        answer = f"Total spent on {item.title()}: ${total:.2f}" if total else f"No purchases found for {item.title()}."
    # List all items
    elif 'list all items' in q or 'show all items' in q:
        c.execute("SELECT name, price, receipt_id FROM items WHERE user_id=?", (USER_ID,))
        items = c.fetchall()
        if items:
            lines = []
            for i in items:
                c.execute("SELECT store, date FROM receipts WHERE user_id=? AND id=?", (USER_ID, i[2]))
                r = c.fetchone()
                if r:
                    lines.append(f"{i[0]}: ${i[1]:.2f} ({r[1]} - {r[0]})")
            answer = "All items:\n" + "\n".join(lines)
        else:
            answer = "No items found."
    # Category/month
    elif 'grocer' in q or 'supermarket' in q or 'food' in q:
        month = None
        for m in ['january','february','march','april','may','june','july','august','september','october','november','december']:
            if m in q:
                month = m
                break
        if month:
            month_num = datetime.strptime(month, '%B').month
            year = now.year
            c.execute("SELECT SUM(total) FROM receipts WHERE user_id=? AND (store LIKE ? OR store LIKE ? OR store LIKE ?) AND strftime('%m', date) = ? AND strftime('%Y', date) = ?", (USER_ID, '%groc%', '%supermarket%', '%food%', f'{month_num:02d}', str(year)))
            total = c.fetchone()[0]
            answer = f"Total groceries in {month.title()}: ${total:.2f}" if total else f"No grocery receipts for {month.title()}."
        else:
            c.execute("SELECT SUM(total) FROM receipts WHERE user_id=? AND (store LIKE ? OR store LIKE ? OR store LIKE ?)", (USER_ID, '%groc%', '%supermarket%', '%food%'))
            total = c.fetchone()[0]
            answer = f"Total groceries: ${total:.2f}" if total else "No grocery receipts found."
    # Total
    elif 'total' in q or 'all' in q or 'everything' in q:
        c.execute("SELECT SUM(total) FROM receipts WHERE user_id=?", (USER_ID,))
        total = c.fetchone()[0]
        answer = f"Total spent: ${total:.2f}" if total else "No receipts found."
    # List receipts
    elif 'list' in q or 'show' in q:
        c.execute("SELECT store, date, total FROM receipts WHERE user_id=? ORDER BY date DESC", (USER_ID,))
        rows = c.fetchall()
        if rows:
            answer = "\n".join([f"{r[1]} - {r[0]}: ${r[2]:.2f}" for r in rows])
        else:
            answer = "No receipts found."
    else:
        answer = "Sorry, I couldn't understand your question. Try asking about totals, vendors, items, or months."
    conn.close()
    return answer

# --- Streamlit UI ---
st.set_page_config(page_title="AI Receipt Analyzer", layout="wide")
st.title("🧾 AI Receipt Analyzer")
st.caption(f"Your private session ID: {USER_ID[:8]}... (keep this tab open to access your receipts)")

# Sidebar: Upload
st.sidebar.header("Upload Receipt")
uploaded_file = st.sidebar.file_uploader("Upload JPG, PNG, or PDF", type=["jpg", "jpeg", "png", "pdf"])

if uploaded_file and "last_uploaded_filename" not in st.session_state:
    st.session_state["last_uploaded_filename"] = None

if uploaded_file:
    if uploaded_file.name != st.session_state["last_uploaded_filename"]:
        with st.spinner("Extracting data from receipt..."):
            text = extract_text_from_file(uploaded_file)
            if not text.strip():
                st.sidebar.error("Could not extract any text from the uploaded file. Please try another receipt.")
            else:
                store, date, total, items = parse_receipt_text(text)
                image_bytes = uploaded_file.read() if hasattr(uploaded_file, 'read') else None
                insert_receipt(store, date, total, image_bytes, items)
                st.sidebar.success(f"Receipt from {store} on {date} uploaded!")
                st.session_state["last_uploaded_filename"] = uploaded_file.name
else:
    st.session_state["last_uploaded_filename"] = None

# Sidebar: Export
if st.sidebar.button("Export Receipts to CSV"):
    csv_path, items_csv_path = export_receipts_to_csv()
    with open(csv_path, "rb") as f:
        st.sidebar.download_button("Download Receipts CSV", f, file_name="receipts.csv")
    with open(items_csv_path, "rb") as f:
        st.sidebar.download_button("Download Items CSV", f, file_name="items.csv")

# --- Main: Receipts Table with Item Details ---
st.subheader("Uploaded Receipts")
receipts = get_receipts()
if receipts:
    df = pd.DataFrame(receipts, columns=["ID", "Vendor", "Date", "Total"])
    st.dataframe(df, use_container_width=True)
    for r in receipts:
        total_str = f"${r[3]:.2f}" if r[3] is not None else "N/A"
        with st.expander(f"Details for {r[2]} - {r[1]}: {total_str}"):
            items = get_items_for_receipt(r[0])
            if items:
                st.write(pd.DataFrame(items, columns=["Item", "Price"]))
            else:
                st.write("No items found for this receipt.")
    del_id = st.selectbox("Select receipt to delete", ["None"] + [str(r[0]) for r in receipts], key="delete_select")
    if del_id != "None":
        if st.button("Delete Selected Receipt", key="delete_btn"):
            delete_receipt(int(del_id))
            st.success("Receipt deleted. Please refresh the page to see the update.")
    show_id = st.selectbox("Show items for receipt", ["None"] + [str(r[0]) for r in receipts], key="show_select")
    if show_id != "None":
        items = get_items_for_receipt(int(show_id))
        if items:
            st.write(pd.DataFrame(items, columns=["Item", "Price"]))
        else:
            st.write("No items found for this receipt.")
else:
    st.info("No receipts uploaded yet.")

# --- Enhanced Chat Interface ---
st.subheader("💬 Ask about your receipts")
user_query = st.text_input("Type your question (e.g. 'How much did I spend this month? Or list all items')", key="chat_input")
if st.button("Ask", key="chat_btn") and user_query:
    with st.spinner("Thinking..."):
        answer = answer_query(user_query)
        st.write(answer)

# --- Monthly Summary ---
st.subheader("📊 Monthly Expense Summary")
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query('SELECT date, total, store FROM receipts WHERE user_id=?', conn, params=(USER_ID,))
conn.close()
if not df.empty:
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['month'] = df['date'].dt.to_period('M')
    summary = df.groupby('month').agg({'total': 'sum'}).reset_index()
    st.bar_chart(summary.set_index('month'))
    vendor_summary = df.groupby(['month', 'store']).agg({'total': 'sum'}).reset_index()
    st.write("### By Vendor/Store")
    st.dataframe(vendor_summary)
else:
    st.info("No data for summary yet.")

st.caption("Built with Streamlit, pytesseract, and SQLite. Your data is private to this browser session.") 