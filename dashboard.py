import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(page_title="SlackDigest Dashboard", layout="wide")

st.title("🚀 SlackDigest AI Triage Dashboard")
st.markdown("AI-powered summarization and triage of high-volume communications.")

import os

# API Base URL - default to localhost for local dev, allow override for Docker
API_URL = os.getenv("API_URL", "http://localhost:8000")

def fetch_stats():
    try:
        response = requests.get(f"{API_URL}/stats")
        return response.json()
    except:
        st.error("Could not connect to FastAPI backend. Make sure it's running on port 8000.")
        return None

def fetch_digest(category=None):
    params = {"category": category} if category else {}
    response = requests.get(f"{API_URL}/digest", params=params)
    return response.json()

stats = fetch_stats()

if stats:
    # Sidebar for filtering
    st.sidebar.header("Filters")
    categories = ["All"] + list(stats['category_distribution'].keys())
    selected_cat = st.sidebar.selectbox("Filter by Category", categories)
    
    # Layout: Top row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📊 Category Distribution")
        fig_pie = px.pie(
            values=list(stats['category_distribution'].values()),
            names=list(stats['category_distribution'].keys()),
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col2:
        st.subheader("📈 Message Volume over Time")
        df_vol = pd.DataFrame(stats['volume_over_time'])
        if not df_vol.empty:
            fig_line = px.line(df_vol, x='date', y='count', markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No volume data available.")
            
    with col3:
        st.subheader("👤 Top User Activity")
        fig_user = px.bar(
            x=list(stats['user_activity'].values()),
            y=list(stats['user_activity'].keys()),
            orientation='h',
            title="Top 10 Most Active Users"
        )
        st.plotly_chart(fig_user, use_container_width=True)

    # Middle Row
    col4, col5 = st.columns(2)
    
    with col4:
        st.subheader("⚠️ Top Priority Items")
        df_top = pd.DataFrame(stats['top_priority_items'])
        st.table(df_top)
        
    with col5:
        st.subheader("🛠️ Channel-wise Action Items")
        df_chan = pd.DataFrame(stats['channel_stats']).T.reset_index().rename(columns={'index': 'channel'})
        if 'Action Item' in df_chan.columns:
            fig_chan = px.bar(df_chan, x='channel', y='Action Item', color='channel')
            st.plotly_chart(fig_chan, use_container_width=True)
        else:
            st.info("No Action Items found.")

    # Bottom Row
    col6, col7 = st.columns(2)
    
    with col6:
        st.subheader("⚡ Urgency vs. Time")
        # For this we need raw data or specific aggregate
        digest = fetch_digest()
        df_digest = pd.DataFrame(digest)
        df_digest['date'] = pd.to_datetime(df_digest['timestamp'], errors='coerce')
        fig_scatter = px.scatter(df_digest, x='date', y='priority', color='category', hover_data=['user', 'channel'])
        st.plotly_chart(fig_scatter, use_container_width=True)
        
    with col7:
        st.subheader("⏱️ Average Response Latency (Synthetic)")
        # Mocking latency data
        latency_data = {"Mon": 12, "Tue": 15, "Wed": 10, "Thu": 18, "Fri": 14}
        fig_lat = px.line(x=list(latency_data.keys()), y=list(latency_data.values()), title="Minutes to Triage")
        st.plotly_chart(fig_lat, use_container_width=True)

    # Full Digest Table
    st.subheader("📋 Message Digest")
    display_digest = fetch_digest(None if selected_cat == "All" else selected_cat)
    st.write(pd.DataFrame(display_digest)[['timestamp', 'user', 'channel', 'category', 'priority', 'text']])

else:
    st.warning("Waiting for data from API...")
