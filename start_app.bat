@echo off
python -m venv venv
call venv\Scripts\activate
git pull
pip install -r requirements.txt
streamlit run dashboard/app.py
