#!/bin/bash
python3 -m venv venv
source venv/bin/activate
git pull
pip install -r requirements.txt
streamlit run streamlit_app.py
