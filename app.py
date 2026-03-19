import os
from dotenv import load_dotenv

# Activate the hidden .env file so Python can read it
load_dotenv()

import streamlit as st
import requests
import json
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.title("Nilay's BI Analyst AI Assistant")

# --- PRODUCTION WEBHOOK URL ---
# Fetch the webhook URL from the .env file, or use a local placeholder for public display
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/your-webhook-id")

# Load the local Excel dataset
@st.cache_data
def load_data():
    # Notice there is no "../" here anymore, because the file is in the exact same folder!
    df = pd.read_excel("Agentic_BI_Raw_Data.xlsx")
    df.columns = df.columns.str.strip()
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Error loading Excel file: {e}")
    st.stop()

# --- INITIALIZE SESSION STATE & TRACKERS ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "request_count" not in st.session_state:
    st.session_state.request_count = 0
if "last_request_time" not in st.session_state:
    st.session_state.last_request_time = 0

# --- API USAGE MONITOR (SIDEBAR) ---
with st.sidebar:
    st.header("📊 API Usage Monitor")
    st.caption("Local session tracker to help avoid Gemini Free Tier limits.")
    
    st.metric(label="Requests Sent (This Session)", value=st.session_state.request_count)
    
    # Calculate cooldown to avoid the strict Requests Per Minute (RPM) limit
    elapsed = time.time() - st.session_state.last_request_time
    if st.session_state.last_request_time == 0 or elapsed > 12:
        st.success("🟢 API Status: Ready")
    else:
        # Recommends a 12-second pause (supports 5 RPM limit for Gemini 2.5 Pro)
        cooldown_left = 12 - int(elapsed)
        st.warning(f"🟡 API Cooldown: Please wait {cooldown_left}s to avoid rate limits.")
        
    st.markdown("---")
    st.markdown("""
    **Gemini Free Tier Limits (Mar 2026):**
    - **2.5 Pro:** 5 Req / Min | 100 Req / Day
    - **2.5 Flash:** 10 Req / Min | 250 Req / Day
    
    *Daily limits reset at exactly 1:30 PM IST.*
    """)

# --- 1. UI RENDERING ENGINE (DRY Code) ---
def render_message(msg, index):
    """Handles rendering text, tables, and interactive charts dynamically."""
    if msg["type"] == "text":
        st.write(msg["content"])
        
    elif msg["type"] == "dataframe":
        st.dataframe(msg["content"], use_container_width=True)
        csv_data = msg["content"].to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download CSV", data=csv_data, file_name=f"export_{index}.csv", mime="text/csv", key=f"dl_csv_{index}")
        
    elif msg["type"] == "chart":
        # --- BACKWARDS COMPATIBILITY ---
        if "data" not in msg:
            st.plotly_chart(msg["content"], use_container_width=True, key=f"old_chart_{index}")
            if "timer" in msg:
                st.caption(f"⏱️ Processed in {msg['timer']:.2f} seconds.")
            return
        # ----------------------------------------
        
        df_chart = msg["data"].copy()
        x_col = msg["x_col"]
        y_cols = msg.get("y_cols", [msg.get("y_col")]) # Upgraded to support multiple y columns
        y_val = y_cols[0] # Primary metric
        c_type = msg["chart_type"]
        title = msg["title"]
        
        # Native Streamlit Dropdowns for Sorting, Base Color, and Average Line (Now 5 Columns!)
        cols = st.columns(5)
        with cols[0]:
            sort_axis = st.selectbox("Sort Axis:", [x_col] + y_cols, key=f"sort_axis_{index}")
        with cols[1]:
            sort_order = st.selectbox("Sort Order:", ["None", "Ascending", "Descending"], index=0, key=f"sort_order_{index}")
        with cols[2]:
            base_color = st.color_picker("Base Color:", value="#1f77b4", key=f"base_color_{index}")
        with cols[3]:
            st.write("") # Spacing to align perfectly with the dropdowns
            st.write("")
            show_avg = st.checkbox("Show Average", key=f"show_avg_{index}")
        with cols[4]:
            avg_color = st.color_picker("Avg Line Color:", value="#e74c3c", key=f"avg_color_{index}")
        
        # Apply the chosen sorting parameters instantly
        if sort_order != "None":
            asc = True if sort_order == "Ascending" else False
            df_chart = df_chart.sort_values(by=sort_axis, ascending=asc)

        # Smart Coloring Logic (Base Color vs Highlights)
        category_colors = {}
        unique_categories = df_chart[x_col].unique()
        highlight_cats = []
        
        with st.expander("🎨 Highlight / Customize Colors"):
            if c_type == "pie":
                st.write("Customize individual slice colors:")
                default_palette = px.colors.qualitative.Plotly * (len(unique_categories) // len(px.colors.qualitative.Plotly) + 1)
                picker_cols = st.columns(4)
                for i, cat in enumerate(unique_categories):
                    cat_str = str(cat)
                    default_hex = base_color if i == 0 else default_palette[i]
                    with picker_cols[i % 4]:
                        category_colors[cat] = st.color_picker(cat_str, value=default_hex, key=f"color_{index}_{cat_str}")
            else:
                st.write("Highlight specific bars (overrides Base Color):")
                highlight_cats = st.multiselect("Select categories to highlight:", unique_categories, key=f"hl_cats_{index}")
                if highlight_cats:
                    picker_cols = st.columns(4)
                    for i, cat in enumerate(highlight_cats):
                        cat_str = str(cat)
                        with picker_cols[i % 4]:
                            category_colors[cat] = st.color_picker(cat_str, value="#ff7f0e", key=f"hl_color_{index}_{cat_str}")
            
        # Render the correct chart orientation and colors!
        cat_array = df_chart[x_col].tolist()

        # ADVANCED: Mixed Dual-Axis Chart (Bar + Line Overlay)
        if c_type == "mixed" and len(y_cols) >= 2:
            y1, y2 = y_cols[0], y_cols[1]
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(go.Bar(x=df_chart[x_col], y=df_chart[y1], name=y1, marker_color=base_color), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_chart[x_col], y=df_chart[y2], name=y2, mode='lines+markers', line=dict(color='#ff7f0e', width=3)), secondary_y=True)
            
            fig.update_layout(title=title, barmode='group', showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=cat_array)
            fig.update_yaxes(title_text=y1, secondary_y=False)
            fig.update_yaxes(title_text=y2, secondary_y=True)
            
            if show_avg:
                avg_val = df_chart[y1].mean()
                fig.add_hline(y=avg_val, line_dash="dash", line_color=avg_color, annotation_text=f"Avg {y1}: {avg_val:,.1f}", secondary_y=False)
                
        # ADVANCED: Standard Clustered Chart
        elif len(y_cols) >= 2:
            fig = px.bar(df_chart, x=x_col, y=y_cols, title=title, barmode='group', color_discrete_sequence=[base_color, '#ff7f0e', '#2ca02c'])
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=cat_array)
            if show_avg:
                avg_val = df_chart[y_cols[0]].mean()
                fig.add_hline(y=avg_val, line_dash="dash", line_color=avg_color, annotation_text=f"Avg {y_cols[0]}: {avg_val:,.1f}")

        # STANDARD CHARTS (Single Metric)
        elif c_type == "pie":
            fig = px.pie(df_chart, names=x_col, values=y_val, title=title, color=x_col, color_discrete_map=category_colors)
            fig.update_traces(textposition='inside', textinfo='percent+label+value')
        elif c_type == "bar": 
            if highlight_cats:
                full_color_map = {cat: category_colors.get(cat, base_color) for cat in unique_categories}
                fig = px.bar(df_chart, x=y_val, y=x_col, orientation='h', title=title, text_auto=True, color=x_col, color_discrete_map=full_color_map)
            else:
                fig = px.bar(df_chart, x=y_val, y=x_col, orientation='h', title=title, text_auto=True, color_discrete_sequence=[base_color])
            
            fig.update_yaxes(type='category', categoryorder='array', categoryarray=cat_array[::-1]) 
            fig.update_layout(showlegend=False)
            
            if show_avg:
                avg_val = df_chart[y_val].mean()
                fig.add_vline(x=avg_val, line_dash="dash", line_color=avg_color, annotation_text=f"Avg: {avg_val:,.1f}", annotation_position="bottom right")
        else: 
            if highlight_cats:
                full_color_map = {cat: category_colors.get(cat, base_color) for cat in unique_categories}
                fig = px.bar(df_chart, x=x_col, y=y_val, title=title, text_auto=True, color=x_col, color_discrete_map=full_color_map)
            else:
                fig = px.bar(df_chart, x=x_col, y=y_val, title=title, text_auto=True, color_discrete_sequence=[base_color])
            
            fig.update_xaxes(type='category', categoryorder='array', categoryarray=cat_array)
            fig.update_layout(showlegend=False)
            
            if show_avg:
                avg_val = df_chart[y_val].mean()
                fig.add_hline(y=avg_val, line_dash="dash", line_color=avg_color, annotation_text=f"Avg: {avg_val:,.1f}", annotation_position="top right")
            
        st.plotly_chart(fig, use_container_width=True, key=f"plotly_fig_{index}")
        
    if "timer" in msg:
        st.caption(f"⏱️ Processed in {msg['timer']:.2f} seconds.")

# --- 2. RENDER HISTORICAL CONVERSATION ---
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        render_message(msg, i)

# --- 3. HANDLE NEW CHAT INPUT ---
if prompt := st.chat_input("Ask for a chart, table, or summary..."):
    
    # Check if the user is typing too fast (prevents the 429 error crash)
    elapsed = time.time() - st.session_state.last_request_time
    if st.session_state.last_request_time != 0 and elapsed < 12:
        st.warning(f"⚠️ **Rate Limit Warning:** Please wait {12 - int(elapsed)} seconds before sending your next request to protect your free API quota.")
        st.stop()
        
    new_user_msg = {"role": "user", "type": "text", "content": prompt}
    st.session_state.messages.append(new_user_msg)
    with st.chat_message("user"):
        render_message(new_user_msg, len(st.session_state.messages) - 1)
        
    with st.chat_message("assistant"):
        with st.spinner("Processing request... (Please wait)"):
            start_time = time.time()
            
            # --- UPDATE API TRACKERS IMMEDIATELY ---
            st.session_state.request_count += 1
            st.session_state.last_request_time = time.time()
            
            try:
                response = requests.post(N8N_WEBHOOK_URL, json={"chatInput": prompt})
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    raw_output = response.json().get("output", "").strip()
                    
                    if raw_output.startswith("```json"): 
                        raw_output = raw_output[7:]
                    if raw_output.startswith("```"): 
                        raw_output = raw_output[3:]
                    if raw_output.endswith("```"): 
                        raw_output = raw_output[:-3]
                    
                    raw_output = raw_output.strip()
                    
                    try:
                        blueprint = json.loads(raw_output)
                        
                        response_type = blueprint.get("response_type", "chart") 
                        
                        if response_type == "summary":
                            summary = blueprint.get("summary_text", "Here is the summary.")
                            new_msg = {"role": "assistant", "type": "text", "content": summary, "timer": duration}
                            
                        else:
                            x_col = blueprint.get("x_column", "").strip()
                            
                            # MULTI-METRIC SUPPORT
                            y_raw = blueprint.get("y_column", "")
                            if isinstance(y_raw, list):
                                y_cols = [str(y).strip() for y in y_raw]
                            else:
                                y_cols = [y.strip() for y in str(y_raw).split(",")] if "," in str(y_raw) else [str(y_raw).strip()]
                                
                            chart_type = blueprint.get("chart_type", "column").lower()
                            
                            if len(y_cols) > 1 and ("mixed" in prompt.lower() or "line" in prompt.lower()):
                                chart_type = "mixed"

                            filter_col = blueprint.get("filter_column")
                            filter_val = blueprint.get("filter_value")
                            
                            filtered_df = df.copy()
                            if filter_col and filter_val and filter_col in df.columns:
                                filtered_df = filtered_df[filtered_df[filter_col].astype(str).str.contains(str(filter_val), case=False, na=False, regex=False)]
                                
                            # SMART DATE HANDLING & DYNAMIC RENAMING
                            if x_col in filtered_df.columns:
                                if filtered_df[x_col].dtype == 'object':
                                    try:
                                        sample_val = str(filtered_df[x_col].dropna().iloc[0])
                                        if any(c.isdigit() for c in sample_val) and ('-' in sample_val or '/' in sample_val):
                                            filtered_df[x_col] = pd.to_datetime(filtered_df[x_col], errors='ignore')
                                    except:
                                        pass
                                
                                if pd.api.types.is_datetime64_any_dtype(filtered_df[x_col]):
                                    if "year" in prompt.lower():
                                        filtered_df["Year"] = filtered_df[x_col].dt.year.astype(str)
                                        x_col = "Year" 
                                    elif "month" in prompt.lower():
                                        filtered_df["Month"] = filtered_df[x_col].dt.strftime('%Y-%m')
                                        x_col = "Month"
                                    else:
                                        filtered_df["Date"] = filtered_df[x_col].dt.strftime('%Y-%m-%d')
                                        x_col = "Date"
                                        
                            agg_df = filtered_df.groupby(x_col)[y_cols].sum().reset_index()
                            
                            if response_type == "table":
                                new_msg = {"role": "assistant", "type": "dataframe", "content": agg_df, "timer": duration}
                                
                            elif response_type == "chart":
                                title_y = y_cols[0] if len(y_cols) == 1 else f"{y_cols[0]} & {y_cols[1]}"
                                title = f"Total {title_y} by {x_col}"
                                new_msg = {
                                    "role": "assistant", 
                                    "type": "chart", 
                                    "data": agg_df,
                                    "x_col": x_col,
                                    "y_cols": y_cols,
                                    "chart_type": chart_type, 
                                    "title": title,
                                    "timer": duration
                                }
                            else:
                                new_msg = {"role": "assistant", "type": "text", "content": "Unknown response routing.", "timer": duration}

                        st.session_state.messages.append(new_msg)
                        render_message(new_msg, len(st.session_state.messages) - 1)
                                
                    except json.JSONDecodeError:
                        error_msg = f"The AI did not return a valid blueprint. Raw output:\n{raw_output}"
                        new_msg = {"role": "assistant", "type": "text", "content": error_msg, "timer": duration}
                        st.session_state.messages.append(new_msg)
                        render_message(new_msg, len(st.session_state.messages) - 1)
                    except Exception as e:
                        error_msg = f"Pandas processing error: {e}"
                        new_msg = {"role": "assistant", "type": "text", "content": error_msg, "timer": duration}
                        st.session_state.messages.append(new_msg)
                        render_message(new_msg, len(st.session_state.messages) - 1)
                else:
                    error_msg = f"Error: n8n returned status code {response.status_code}."
                    new_msg = {"role": "assistant", "type": "text", "content": error_msg}
                    st.session_state.messages.append(new_msg)
                    render_message(new_msg, len(st.session_state.messages) - 1)
            except requests.exceptions.RequestException as e:
                error_msg = f"Network Error: {e}"
                new_msg = {"role": "assistant", "type": "text", "content": error_msg}
                st.session_state.messages.append(new_msg)
                render_message(new_msg, len(st.session_state.messages) - 1)
                
            st.rerun() # Refresh to update the Sidebar UI counter
        
