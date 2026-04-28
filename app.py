# Project : DealOrDud — Fake Discount Detector
# Author  : Anshika Goyal
# Purpose : Interactive Streamlit dashboard to explore and visualise
#           the scraped price history and fake discount analysis
# ═════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="DealOrDud — Fake Discount Detector",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #FF6B35;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-top: 0;
        margin-bottom: 2rem;
    }

    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
    }

    .fake-row { background-color: #fff3cd; }
</style>
""", unsafe_allow_html=True)

DATA_CANDIDATES = [
    Path("price_history.csv"),
    Path("data/price_history.csv"),
    Path("data/amazon_discount_history.csv"),
    Path("amazon_discount_history.csv"),
]


def find_data_file() -> Path | None:

    for path in DATA_CANDIDATES:
        if path.exists():
            return path
    return None


@st.cache_data(ttl=3600)
def load_data() -> tuple[pd.DataFrame | None, Path | None]:

    data_path = find_data_file()
    if data_path is None:
        return None, None

    df = pd.read_csv(data_path)

    rename_map = {
        "scraped_at": "scraped_at_utc",
        "url": "product_url",
        "current_price": "discounted_price",
        "displayed_discount_pct": "displayed_discount_percent",
        "computed_discount_pct": "computed_discount_percent",
        "fake_discount": "fake_discount_flag",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    required_defaults = {
        "scraped_at_utc": None,
        "product_name": "Unknown product",
        "product_url": "",
        "mrp": None,
        "discounted_price": None,
        "displayed_discount_percent": None,
        "computed_discount_percent": None,
        "fake_discount_flag": False,
        "analysis_note": "",
        "in_stock": True,
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    parsed_ts = pd.to_datetime(df["scraped_at_utc"], errors="coerce")

    try:
        if parsed_ts.dt.tz is None:
            parsed_ts = parsed_ts.dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")
        else:
            parsed_ts = parsed_ts.dt.tz_convert("UTC")
    except Exception:
        pass

    df["scraped_at_utc"] = parsed_ts
    df["date"] = df["scraped_at_utc"].dt.date

    for col in ["mrp", "discounted_price", "displayed_discount_percent", "computed_discount_percent"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["fake_discount_flag"] = (
        df["fake_discount_flag"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "false": False,
            "1": True,
            "0": False,
            "yes": True,
            "no": False,
        })
        .fillna(False)
    )

    return df, data_path

st.markdown('<p class="main-header">🛒 DealOrDud</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Are Amazon India discounts real? '
    'We track prices daily and show you the truth.</p>',
    unsafe_allow_html=True,
)
st.divider()

df, active_data_path = load_data()

if df is None or df.empty:
    st.warning("⚠️ No data collected yet.")
    st.info("""
    **To get started:**

    **Step 1 — Run your scraper to create the dataset:**
    ```bash
    python scraper.py
    ```

    **Step 2 — Run this dashboard:**
    ```bash
    streamlit run app.py
    ```

    **This app automatically looks for these files:**
    - `price_history.csv`
    - `data/price_history.csv`
    - `data/amazon_discount_history.csv`

    Data will appear here after the first successful scrape run.
    """)
    st.stop()

st.sidebar.header("🔍 Filters")

min_date = df["date"].min()
max_date = df["date"].max()

date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    help="Filter data to a specific date range",
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range if not isinstance(date_range, tuple) else date_range[0]

df_filtered = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

show_fake_only = st.sidebar.toggle(
    "⚠️ Show fake discounts only",
    value=False,
    help="When enabled, only shows products flagged as having misleading discounts",
)

if show_fake_only:
    df_filtered = df_filtered[df_filtered["fake_discount_flag"] == True]

search_query = st.sidebar.text_input(
    "🔎 Search product name",
    placeholder="e.g. boAt, headphones...",
    help="Filter products by name",
)

if search_query:
    df_filtered = df_filtered[
        df_filtered["product_name"].str.contains(search_query, case=False, na=False)
    ]

st.sidebar.divider()
st.sidebar.caption(f"Showing **{len(df_filtered):,}** of **{len(df):,}** records")
st.sidebar.caption(f"Dataset: {active_data_path if active_data_path else 'No file found'}")

st.subheader("📊 Overview")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

with kpi1:
    unique_products = df_filtered["product_url"].nunique()
    st.metric(
        label="Products Tracked",
        value=f"{unique_products:,}",
        help="Number of unique Amazon products in the selected date range",
    )

with kpi2:
    st.metric(
        label="Price Records",
        value=f"{len(df_filtered):,}",
        help="Total number of daily price observations collected",
    )

with kpi3:
    fake_count = df_filtered["fake_discount_flag"].sum()
    fake_pct = (fake_count / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
    st.metric(
        label="Fake Discounts",
        value=f"{fake_count:,}",
        delta=f"{fake_pct:.1f}% of records",
        delta_color="inverse",
        help="Products where computed discount differs from displayed discount by 2%+",
    )

with kpi4:
    avg_displayed = df_filtered["displayed_discount_percent"].mean()
    st.metric(
        label="Avg Displayed Discount",
        value=f"{avg_displayed:.1f}%" if pd.notna(avg_displayed) else "N/A",
        help="Average discount percentage Amazon claims across all tracked products",
    )

with kpi5:
    avg_computed = df_filtered["computed_discount_percent"].mean()
    diff = avg_displayed - avg_computed if pd.notna(avg_displayed) and pd.notna(avg_computed) else None
    st.metric(
        label="Avg Real Discount",
        value=f"{avg_computed:.1f}%" if pd.notna(avg_computed) else "N/A",
        delta=f"{diff:.1f}% gap" if diff is not None else None,
        delta_color="inverse",
        help="Average discount we independently compute from MRP and current price",
    )

st.divider()

st.subheader("📈 Trend Analysis")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    daily_stats = (
        df_filtered
        .groupby("date")
        .agg(
            total=("fake_discount_flag", "count"),
            fake=("fake_discount_flag", "sum"),
        )
        .reset_index()
    )
    daily_stats["fake_pct"] = (daily_stats["fake"] / daily_stats["total"] * 100).round(1)

    if not daily_stats.empty:
        fig1 = px.line(
            daily_stats,
            x="date",
            y="fake_pct",
            title="Daily Fake Discount Rate (%)",
            labels={"date": "Date", "fake_pct": "Fake Discount Rate (%)"},
            markers=True,
            line_shape="spline",
            color_discrete_sequence=["#FF6B35"],
        )
        fig1.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
        fig1.update_layout(height=350, margin=dict(t=40, b=20))
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("Not enough data for trend chart yet. Keep the scraper running.")

with chart_col2:
    df_with_gap = df_filtered.copy()
    df_with_gap["discount_gap"] = (
        df_with_gap["displayed_discount_percent"] - df_with_gap["computed_discount_percent"]
    )
    df_with_gap = df_with_gap.dropna(subset=["discount_gap"])

    if not df_with_gap.empty:
        fig2 = px.histogram(
            df_with_gap,
            x="discount_gap",
            nbins=30,
            title="Discount Gap Distribution (Displayed % − Computed %)",
            labels={"discount_gap": "Discount Gap (percentage points)"},
            color_discrete_sequence=["#2196F3"],
        )
        fig2.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="No gap")
        fig2.add_vline(x=2, line_dash="dot", line_color="orange", annotation_text="Fake threshold")
        fig2.update_layout(height=350, margin=dict(t=40, b=20))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Not enough data for gap distribution chart yet.")

st.divider()

st.subheader("📉 Product Price History")

all_products = (
    df_filtered
    .groupby("product_url")["product_name"]
    .first()
    .reset_index()
)
all_products["display_name"] = all_products["product_name"].str[:80]

selected_product_url = st.selectbox(
    "Select a product to view its price history:",
    options=all_products["product_url"].tolist(),
    format_func=lambda url: all_products.loc[
        all_products["product_url"] == url, "display_name"
    ].values[0],
    help="Shows how this product's price and MRP changed over time",
)

if selected_product_url:
    product_history = (
        df_filtered[df_filtered["product_url"] == selected_product_url]
        .sort_values("date")
    )
    product_name = product_history["product_name"].iloc[0]

    if not product_history.empty:
        fig3 = go.Figure()

        fig3.add_trace(go.Scatter(
            x=product_history["date"],
            y=product_history["discounted_price"],
            mode="lines+markers",
            name="Sale Price",
            line=dict(color="#2196F3", width=2),
            marker=dict(size=6),
        ))

        if product_history["mrp"].notna().any():
            fig3.add_trace(go.Scatter(
                x=product_history["date"],
                y=product_history["mrp"],
                mode="lines+markers",
                name="MRP (Original Price)",
                line=dict(color="#9E9E9E", width=2, dash="dash"),
                marker=dict(size=6),
            ))

        fake_days = product_history[product_history["fake_discount_flag"] == True]
        if not fake_days.empty:
            fig3.add_trace(go.Scatter(
                x=fake_days["date"],
                y=fake_days["discounted_price"],
                mode="markers",
                name="⚠ Fake Discount Flagged",
                marker=dict(color="#FF5252", size=12, symbol="x"),
            ))

        fig3.update_layout(
            title=f"Price History: {product_name[:60]}",
            xaxis_title="Date",
            yaxis_title="Price (₹ INR)",
            height=400,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig3, use_container_width=True)

        summary_col1, summary_col2, summary_col3 = st.columns(3)
        with summary_col1:
            latest = product_history.iloc[-1]
            st.metric("Latest Price", f"₹{latest['discounted_price']:,.0f}" if pd.notna(latest['discounted_price']) else "N/A")
        with summary_col2:
            st.metric("Latest MRP", f"₹{latest['mrp']:,.0f}" if pd.notna(latest['mrp']) else "N/A")
        with summary_col3:
            fake_days_count = product_history["fake_discount_flag"].sum()
            st.metric("Days Flagged Fake", f"{fake_days_count} / {len(product_history)}")
    else:
        st.info("No price history data for this product in the selected date range.")

st.divider()

st.subheader("⚠️ Fake Discount Leaderboard")
st.caption("Products with the most misleading discounts detected")

leaderboard = (
    df_filtered[df_filtered["fake_discount_flag"] == True]
    .groupby(["product_name", "product_url"])
    .agg(
        fake_count=("fake_discount_flag", "sum"),
        avg_gap=("computed_discount_percent", lambda x:
            (df_filtered.loc[x.index, "displayed_discount_percent"] - x).mean()
        ),
        latest_price=("discounted_price", "last"),
        latest_mrp=("mrp", "last"),
    )
    .reset_index()
    .sort_values("fake_count", ascending=False)
    .head(15)
)

if not leaderboard.empty:
    display_lb = leaderboard[[
        "product_name", "fake_count", "avg_gap", "latest_price", "latest_mrp"
    ]].copy()
    display_lb.columns = ["Product", "Fake Days", "Avg Discount Gap (%)", "Latest Price (₹)", "MRP (₹)"]
    display_lb["Product"] = display_lb["Product"].str[:60]
    display_lb["Avg Discount Gap (%)"] = display_lb["Avg Discount Gap (%)"].round(1)
    display_lb["Latest Price (₹)"] = display_lb["Latest Price (₹)"].apply(
        lambda x: f"₹{x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_lb["MRP (₹)"] = display_lb["MRP (₹)"].apply(
        lambda x: f"₹{x:,.0f}" if pd.notna(x) else "N/A"
    )

    st.dataframe(
        display_lb,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.success("✅ No fake discounts detected in the selected date range!")

st.divider()

st.subheader("📋 Raw Data")

with st.expander("View full dataset (click to expand)"):
    display_cols = [
        "date", "product_name", "discounted_price", "mrp",
        "displayed_discount_percent", "computed_discount_percent",
        "fake_discount_flag", "analysis_note",
    ]
    display_df = df_filtered[display_cols].copy()

    for col in ["discounted_price", "mrp"]:
        display_df[col] = display_df[col].apply(
            lambda x: f"₹{x:,.0f}" if pd.notna(x) else "N/A"
        )
    for col in ["displayed_discount_percent", "computed_discount_percent"]:
        display_df[col] = display_df[col].apply(
            lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
        )

    st.dataframe(display_df, use_container_width=True, hide_index=True)

csv_download = df_filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download filtered data as CSV",
    data=csv_download,
    file_name=f"dealordud_export_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
    help="Downloads all data currently shown (respects your filters)",
)

st.divider()

last_updated = df["date"].max() if "date" in df.columns and not df.empty else "N/A"

st.caption(
    "DealOrDud — Built by Anshika Goyal | "
    "Data scraped daily from Amazon India | "
    f"Last updated: {last_updated} | "
    "For educational and portfolio purposes"
)
