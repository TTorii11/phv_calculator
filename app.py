import streamlit as st
import datetime
import hashlib
import pandas as pd
import plotly.graph_objects as go
from supabase import create_client, Client

# --- OLDAL BEÁLLÍTÁSAI (Szélesebb, dashboard jellegű elrendezés) ---
st.set_page_config(page_title="PHV & Bio-Banding Dashboard", page_icon="⚽", layout="wide")

# --- EGYEDI CSS STÍLUSOK ---
st.markdown("""
<style>
    /* Fő fejléc banner */
    .hero-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
        padding: 1.8rem 2rem;
        border-radius: 14px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .hero-banner h1 {
        color: white !important;
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    .hero-banner p {
        color: #cbd5e1;
        margin: 0.3rem 0 0 0;
        font-size: 1rem;
    }
    
    /* Metrika kártyák dobozolása */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    
    /* Sötét mód támogatása a kártyákhoz */
    @media (prefers-color-scheme: dark) {
        div[data-testid="stMetric"] {
            background-color: #1e293b;
            border-color: #334155;
        }
    }

    /* Státusz jelvény (Badge) */
    .status-badge {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 10px;
    }
    .badge-early { background-color: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
    .badge-ontime { background-color: #dcfce7; color: #166534; border: 1px solid #4ade80; }
    .badge-late { background-color: #dbeafe; color: #1e40af; border:
