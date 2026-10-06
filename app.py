import io
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Nassau | Profitability Analytics", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

# -----------------------------
# Theme / lightweight product UI
# -----------------------------
st.markdown("""
<style>
:root { --ink:#16202a; --muted:#687684; --line:#e7ebef; --accent:#1f5f78; --accent2:#d97745; --soft:#f5f7f8; }
.block-container { padding-top: 1.25rem; padding-bottom: 2rem; max-width: 1500px; }
section[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
.kicker { color:var(--accent); font-size:.76rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; margin-bottom:.25rem; }
.hero { border-bottom:1px solid var(--line); padding-bottom:1rem; margin-bottom:1rem; }
.hero h1 { margin:.1rem 0 .35rem; font-size:2rem; letter-spacing:-.03em; color:var(--ink); }
.hero p { margin:0; color:var(--muted); max-width:900px; font-size:.96rem; }
.card { background:white; border:1px solid var(--line); border-radius:14px; padding:15px 17px; min-height:112px; box-shadow:0 1px 2px rgba(15,23,42,.03); }
.card-label { color:var(--muted); font-size:.78rem; font-weight:600; margin-bottom:9px; }
.card-value { color:var(--ink); font-size:1.55rem; font-weight:750; letter-spacing:-.02em; }
.card-help { color:var(--muted); font-size:.73rem; margin-top:7px; }
.section-title { color:var(--ink); font-size:1.08rem; font-weight:750; margin:1.1rem 0 .25rem; }
.section-note { color:var(--muted); font-size:.8rem; margin-bottom:.5rem; }
.flag { padding:10px 12px; border:1px solid var(--line); border-radius:10px; background:var(--soft); font-size:.82rem; margin:.35rem 0; }
.small { color:var(--muted); font-size:.75rem; }
div[data-testid="stMetric"] { border:1px solid var(--line); border-radius:14px; padding:12px 14px; background:white; }
button[kind="secondary"] { border-radius:9px; }
</style>
""", unsafe_allow_html=True)

PRODUCT_FACTORY = {
    "Wonka Bar - Nutty Crunch Surprise": "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows": "Lot's O' Nuts",
    "Wonka Bar -Scrumdiddlyumptious": "Lot's O' Nuts",
    "Wonka Bar - Milk Chocolate": "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel": "Wicked Choccy's",
    "Laffy Taffy": "Sugar Shack", "SweeTARTS": "Sugar Shack", "Nerds": "Sugar Shack", "Fun Dip": "Sugar Shack",
    "Fizzy Lifting Drinks": "Sugar Shack", "Everlasting Gobstopper": "Secret Factory", "Hair Toffee": "The Other Factory",
    "Lickable Wallpaper": "Secret Factory", "Wonka Gum": "Secret Factory", "Kazookles": "The Other Factory",
}
FACTORY_COORDS = {
    "Lot's O' Nuts": (32.881893, -111.768036),
    "Wicked Choccy's": (32.076176, -81.088371),
    "Sugar Shack": (48.11914, -96.18115),
    "Secret Factory": (41.446333, -90.565487),
    "The Other Factory": (35.1175, -89.971107),
}

COLUMN_ALIASES = {
    "Row ID": ["row id", "row_id", "rowid"],
    "Order ID": ["order id", "order_id", "orderid"],
    "Order Date": ["order date", "order_date", "date", "orderdate"],
    "Ship Date": ["ship date", "ship_date", "shipdate"],
    "Ship Mode": ["ship mode", "ship_mode", "shipping mode", "shipping_method"],
    "Customer ID": ["customer id", "customer_id", "customerid"],
    "Country/Region": ["country/region", "country", "country region", "country_region"],
    "City": ["city"], "State/Province": ["state/province", "state", "province", "state_province"],
    "Postal Code": ["postal code", "postal_code", "zip", "zip code"],
    "Division": ["division", "category", "product division"], "Region": ["region"],
    "Product ID": ["product id", "product_id", "productid", "sku"],
    "Product Name": ["product name", "product_name", "product", "item"],
    "Sales": ["sales", "revenue", "sales amount", "net sales"],
    "Units": ["units", "quantity", "qty", "units sold"],
    "Gross Profit": ["gross profit", "gross_profit", "profit", "gross margin dollars"],
    "Cost": ["cost", "cogs", "cost of goods sold", "cost amount"],
}

NUMERIC_FIELDS = ["Sales", "Units", "Gross Profit", "Cost"]

@st.cache_data(show_spinner=False)
def read_source(file_bytes: bytes, file_name: str):
    suffix = Path(file_name).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        sheets = pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names
        frames = []
        for sheet in sheets:
            frames.append((sheet, pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet)))
        return frames
    return [(None, pd.read_csv(io.BytesIO(file_bytes)))]


def canonicalize_columns(df):
    lookup = {str(c).strip().lower(): c for c in df.columns}
    rename = {}
    mapping = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            if alias in lookup:
                found = lookup[alias]
                break
        if found is not None:
            rename[found] = canonical
            mapping[canonical] = found
    out = df.rename(columns=rename).copy()
    return out, mapping


def validate_and_prepare(raw):
    df, source_mapping = canonicalize_columns(raw)
    dq = {"source_rows": len(df), "source_columns": len(raw.columns), "excluded_invalid_order_date": 0, "excluded_invalid_ship_date_for_ship_metrics": 0}
    for c in NUMERIC_FIELDS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["Order Date", "Ship Date"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], dayfirst=True, errors="coerce")
    # No silent row rewrite: invalid date rows remain in the dataset; only date-based views exclude them explicitly.
    if "Order Date" in df.columns:
        dq["invalid_order_dates"] = int(df["Order Date"].isna().sum())
    else: dq["invalid_order_dates"] = None
    if "Ship Date" in df.columns:
        dq["invalid_ship_dates"] = int(df["Ship Date"].isna().sum())
    else: dq["invalid_ship_dates"] = None
    dq["duplicate_rows"] = int(df.duplicated().sum())
    for c in ["Row ID", "Order ID"]:
        dq[f"duplicate_{c}"] = int(df[c].duplicated().sum()) if c in df.columns else None
    for c in ["Sales", "Units", "Gross Profit", "Cost"]:
        if c in df.columns:
            dq[f"{c}_missing"] = int(df[c].isna().sum())
            dq[f"{c}_zero"] = int((df[c] == 0).sum())
            dq[f"{c}_negative"] = int((df[c] < 0).sum())
    if all(c in df.columns for c in ["Sales", "Cost", "Gross Profit"]):
        dq["sales_cost_gp_mismatch_gt_0_01"] = int((df["Sales"] - df["Cost"] - df["Gross Profit"]).abs().gt(.01).sum())
    else: dq["sales_cost_gp_mismatch_gt_0_01"] = None
    if all(c in df.columns for c in ["Order Date", "Ship Date"]):
        dq["ship_before_order"] = int((df["Ship Date"] < df["Order Date"]).sum(skipna=True))
        valid = df["Order Date"].notna() & df["Ship Date"].notna()
        dq["ship_lag_min_days"] = float((df.loc[valid,"Ship Date"]-df.loc[valid,"Order Date"]).dt.days.min()) if valid.any() else None
        dq["ship_lag_max_days"] = float((df.loc[valid,"Ship Date"]-df.loc[valid,"Order Date"]).dt.days.max()) if valid.any() else None
    else: dq["ship_before_order"] = None
    return df, source_mapping, dq


def available(df, cols): return all(c in df.columns for c in cols)

def money(x): return "N/A" if pd.isna(x) else f"${x:,.2f}"
def pct(x): return "N/A" if pd.isna(x) else f"{x:.1%}"
def integer(x): return "N/A" if pd.isna(x) else f"{x:,.0f}"

def metric_card(label, value, help_text=""):
    st.markdown(f'<div class="card"><div class="card-label">{label}</div><div class="card-value">{value}</div><div class="card-help">{help_text}</div></div>', unsafe_allow_html=True)


def aggregate(df, group_cols):
    aggs = {}
    if "Sales" in df: aggs["Revenue"] = ("Sales", "sum")
    if "Cost" in df: aggs["Cost"] = ("Cost", "sum")
    if "Gross Profit" in df: aggs["Gross Profit"] = ("Gross Profit", "sum")
    if "Units" in df: aggs["Units"] = ("Units", "sum")
    out = df.groupby(group_cols, dropna=False).agg(**aggs).reset_index()
    if "Gross Profit" not in out.columns and available(df,["Sales","Cost"]):
        out["Gross Profit"] = out["Revenue"] - out["Cost"]
        out["Gross Profit Basis"] = "Derived: Sales - Cost"
    if "Revenue" in out.columns and "Gross Profit" in out.columns:
        out["Weighted Margin"] = np.where(out["Revenue"] != 0, out["Gross Profit"] / out["Revenue"], np.nan)
    if "Units" in out.columns and "Gross Profit" in out.columns:
        out["Profit / Unit"] = np.where(out["Units"] != 0, out["Gross Profit"] / out["Units"], np.nan)
    return out


def render_header(title, description):
    st.markdown(f'<div class="hero"><div class="kicker">Nassau Candy Distributor · Analytics</div><h1>{title}</h1><p>{description}</p></div>', unsafe_allow_html=True)


def filters(df):
    with st.sidebar:
        st.markdown("### Control panel")
        if st.button("Reset filters", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("flt_"): del st.session_state[k]
            st.rerun()
        st.caption("All pages use the active filter state. Thresholds are analytical controls, not business facts.")
        if "Order Date" in df.columns and df["Order Date"].notna().any():
            mn, mx = df["Order Date"].min().date(), df["Order Date"].max().date()
            dr = st.date_input("Order date range", (mn, mx), min_value=mn, max_value=mx, key="flt_date")
        else: dr = None
        division = st.multiselect("Division", sorted(df["Division"].dropna().unique()) if "Division" in df else [], key="flt_div")
        region = st.multiselect("Region", sorted(df["Region"].dropna().unique()) if "Region" in df else [], key="flt_region")
        states = st.multiselect("State / Province", sorted(df["State/Province"].dropna().unique()) if "State/Province" in df else [], key="flt_state")
        search = st.text_input("Product search", key="flt_product", placeholder="e.g. Milk Chocolate")
        min_margin = st.slider("Minimum margin threshold", 0, 100, 0, 1, format="%d%%", key="flt_margin") / 100
        st.divider()
        st.markdown("**Review rules**")
        high_rev = st.slider("High-revenue percentile", 50, 95, 75, 5, key="flt_high_rev")
        low_margin = st.slider("Low-margin threshold", 0, 100, 20, 1, format="%d%%", key="flt_low_margin") / 100
    mask = pd.Series(True, index=df.index)
    if dr and len(dr)==2 and "Order Date" in df:
        mask &= df["Order Date"].between(pd.Timestamp(dr[0]), pd.Timestamp(dr[1])+pd.Timedelta(days=1)-pd.Timedelta(microseconds=1))
    if division and "Division" in df: mask &= df["Division"].isin(division)
    if region and "Region" in df: mask &= df["Region"].isin(region)
    if states and "State/Province" in df: mask &= df["State/Province"].isin(states)
    if search and "Product Name" in df: mask &= df["Product Name"].astype(str).str.contains(search, case=False, na=False)
    return df.loc[mask].copy(), {"min_margin":min_margin,"high_rev_pct":high_rev,"low_margin":low_margin}


def overview(df, rules):
    render_header("Executive Overview", "A decision-oriented view of revenue, gross profit and margin performance. Metrics respond to the active filters in the sidebar.")
    if df.empty: st.warning("No records match the current filters."); return
    supported = [c for c in ["Sales","Gross Profit","Cost","Units"] if c in df.columns]
    total_sales = df["Sales"].sum() if "Sales" in df else np.nan
    gp = df["Gross Profit"].sum() if "Gross Profit" in df else ((df["Sales"]-df["Cost"]).sum() if available(df,["Sales","Cost"]) else np.nan)
    units = df["Units"].sum() if "Units" in df else np.nan
    products = df["Product ID"].nunique() if "Product ID" in df else (df["Product Name"].nunique() if "Product Name" in df else np.nan)
    margin = gp/total_sales if pd.notna(total_sales) and total_sales != 0 else np.nan
    cols=st.columns(5)
    vals=[("Revenue",money(total_sales),"Sum of Sales"),("Gross Profit",money(gp),"Source Gross Profit" if "Gross Profit" in df else "Derived: Sales − Cost"),("Weighted Gross Margin",pct(margin),"Total GP ÷ total Sales"),("Units",integer(units),"Sum of Units"),("Products",integer(products),"Distinct products in filtered data")]
    for c,(l,v,h) in zip(cols,vals):
        with c: metric_card(l,v,h)
    if "Order Date" in df and "Sales" in df and "Gross Profit" in df:
        st.markdown('<div class="section-title">Performance over time</div><div class="section-note">Monthly aggregation. Margin is weighted: monthly gross profit divided by monthly sales.</div>',unsafe_allow_html=True)
        t=df.dropna(subset=["Order Date"]).assign(Month=lambda x:x["Order Date"].dt.to_period("M").dt.to_timestamp()).groupby("Month").agg(Revenue=("Sales","sum"),Gross_Profit=("Gross Profit","sum")).reset_index()
        t["Margin"]=np.where(t.Revenue!=0,t.Gross_Profit/t.Revenue,np.nan)
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=t.Month,y=t.Revenue,name="Revenue",mode="lines+markers",line=dict(width=2.5)))
        fig.add_trace(go.Scatter(x=t.Month,y=t.Gross_Profit,name="Gross Profit",mode="lines+markers",line=dict(width=2)))
        fig.update_layout(height=360,margin=dict(l=10,r=10,t=20,b=10),hovermode="x unified",legend=dict(orientation="h",y=1.08),yaxis_title="USD")
        st.plotly_chart(fig,use_container_width=True)
    c1,c2=st.columns(2)
    if "Division" in df:
        div=aggregate(df,["Division"])
        with c1:
            st.markdown('<div class="section-title">Division revenue and gross profit</div><div class="section-note">Side-by-side comparison at division level.</div>',unsafe_allow_html=True)
            long=div.melt(id_vars="Division",value_vars=[x for x in ["Revenue","Gross Profit"] if x in div],var_name="Metric",value_name="Amount")
            fig=px.bar(long,x="Division",y="Amount",color="Metric",barmode="group",height=330)
            fig.update_layout(margin=dict(l=10,r=10,t=10,b=10),yaxis_title="USD",legend_title="")
            st.plotly_chart(fig,use_container_width=True)
    if "Division" in df and "Gross Profit" in df:
        with c2:
            st.markdown('<div class="section-title">Transparent observations</div><div class="section-note">Generated from the filtered data using explicit ranking rules.</div>',unsafe_allow_html=True)
            div=aggregate(df,["Division"]).sort_values("Gross Profit",ascending=False)
            if not div.empty:
                st.markdown(f'<div class="flag">Highest gross profit division: <b>{div.iloc[0]["Division"]}</b> ({money(div.iloc[0]["Gross Profit"])}).</div>',unsafe_allow_html=True)
                m=div.sort_values("Weighted Margin",ascending=False).iloc[0]
                st.markdown(f'<div class="flag">Highest weighted margin division: <b>{m["Division"]}</b> ({pct(m["Weighted Margin"])}).</div>',unsafe_allow_html=True)
                if "Product Name" in df:
                    p=aggregate(df,["Product Name"]).sort_values("Gross Profit",ascending=False).iloc[0]
                    st.markdown(f'<div class="flag">Top product by gross profit: <b>{p["Product Name"]}</b> ({money(p["Gross Profit"])}).</div>',unsafe_allow_html=True)
            st.caption("These are descriptive rankings only; they do not establish causality or a business recommendation.")


def product_page(df, rules):
    render_header("Product Profitability", "Compare product economics at the product aggregation level. Use the review thresholds to make the screening rule explicit and adjustable.")
    if not available(df,["Product Name","Sales","Gross Profit","Units"]):
        st.info("Product profitability requires Product Name, Sales, Gross Profit and Units (or equivalent mapped fields).")
        return
    p=aggregate(df,["Division","Product Name"])
    total_rev=p.Revenue.sum() if "Revenue" in p else np.nan; total_gp=p["Gross Profit"].sum()
    p["Revenue Contribution"]=np.where(total_rev!=0,p.Revenue/total_rev,np.nan)
    p["Profit Contribution"]=np.where(total_gp!=0,p["Gross Profit"]/total_gp,np.nan)
    rev_cut=p.Revenue.quantile(rules["high_rev_pct"]/100)
    p["Review Category"]=np.select([
        (p.Revenue>=rev_cut)&(p["Weighted Margin"]<rules["low_margin"]),
        (p.Revenue>=rev_cut)&(p["Weighted Margin"]>=rules["low_margin"]),
        (p.Revenue<rev_cut)&(p["Gross Profit"]>=p["Gross Profit"].median()),
    ],["High revenue / low margin","High revenue / healthy margin","Lower revenue / higher profit"],default="Lower revenue / lower profit")
    p=p[p["Weighted Margin"].fillna(-np.inf)>=rules["min_margin"]]
    if p.empty: st.warning("No products meet the current minimum-margin filter."); return
    st.markdown(f'<div class="section-note">High revenue = ≥ {rules["high_rev_pct"]}th percentile of filtered product revenue ({money(rev_cut)}). Low margin = < {rules["low_margin"]:.0%}. These are screening rules, not objective business classifications.</div>',unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        fig=px.scatter(p,x="Revenue",y="Weighted Margin",size="Gross Profit",color="Division",hover_name="Product Name",height=390)
        fig.update_layout(margin=dict(l=10,r=10,t=10,b=10),yaxis_tickformat=".0%",xaxis_title="Revenue (USD)",yaxis_title="Weighted gross margin")
        st.plotly_chart(fig,use_container_width=True)
    with c2:
        rank=p.sort_values("Gross Profit",ascending=True)
        fig=px.bar(rank,x="Gross Profit",y="Product Name",color="Weighted Margin",orientation="h",height=390)
        fig.update_layout(margin=dict(l=10,r=10,t=10,b=10),xaxis_title="Gross profit (USD)",yaxis_title="")
        st.plotly_chart(fig,use_container_width=True)
    cols=[c for c in ["Division","Product Name","Revenue","Cost","Gross Profit","Weighted Margin","Units","Profit / Unit","Revenue Contribution","Profit Contribution","Review Category"] if c in p]
    show=p[cols].sort_values("Gross Profit",ascending=False).copy()
    for c in ["Weighted Margin","Revenue Contribution","Profit Contribution"]:
        if c in show: show[c]=show[c].map(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    st.dataframe(show,use_container_width=True,hide_index=True,column_config={"Revenue":st.column_config.NumberColumn(format="$%.2f"),"Cost":st.column_config.NumberColumn(format="$%.2f"),"Gross Profit":st.column_config.NumberColumn(format="$%.2f"),"Profit / Unit":st.column_config.NumberColumn(format="$%.2f")})


def division_page(df, rules):
    render_header("Division Performance", "Understand how Chocolate, Sugar and Other contribute to revenue, profit and margin—where those fields exist in the active dataset.")
    if not available(df,["Division","Sales","Gross Profit"]): st.info("Division performance requires Division, Sales and Gross Profit (or derivable Gross Profit)."); return
    d=aggregate(df,["Division"])
    c1,c2=st.columns(2)
    with c1:
        long=d.melt(id_vars="Division",value_vars=["Revenue","Gross Profit"],var_name="Metric",value_name="Amount")
        fig=px.bar(long,x="Division",y="Amount",color="Metric",barmode="group",height=360)
        fig.update_layout(margin=dict(l=10,r=10,t=20,b=10),yaxis_title="USD",legend_title="")
        st.plotly_chart(fig,use_container_width=True)
    with c2:
        fig=px.bar(d.sort_values("Weighted Margin"),x="Weighted Margin",y="Division",orientation="h",text="Weighted Margin",height=360)
        fig.update_traces(texttemplate="%{text:.1%}",textposition="outside")
        fig.update_layout(margin=dict(l=10,r=10,t=20,b=10),xaxis_tickformat=".0%",xaxis_title="Weighted gross margin",yaxis_title="")
        st.plotly_chart(fig,use_container_width=True)
    st.dataframe(d.sort_values("Gross Profit",ascending=False),use_container_width=True,hide_index=True,column_config={"Revenue":st.column_config.NumberColumn(format="$%.2f"),"Cost":st.column_config.NumberColumn(format="$%.2f"),"Gross Profit":st.column_config.NumberColumn(format="$%.2f"),"Weighted Margin":st.column_config.NumberColumn(format="%.1%"),"Profit / Unit":st.column_config.NumberColumn(format="$%.2f")})
    low=d[d["Weighted Margin"]<rules["low_margin"]]
    if not low.empty:
        st.markdown(f'<div class="flag">Screening rule: {len(low)} division(s) fall below the configurable {rules["low_margin"]:.0%} margin threshold. This is a prompt for investigation, not a definitive diagnosis.</div>',unsafe_allow_html=True)


def diagnostics_page(df, rules, dq):
    render_header("Cost & Margin Diagnostics", "A diagnostic layer for cost intensity, margin quality and review flags. Flags are transparent screening prompts, not conclusions.")
    if not available(df,["Sales","Cost","Gross Profit"]): st.info("Diagnostics require Sales, Cost and Gross Profit (or Sales + Cost to derive profit)."); return
    x=df.copy(); x["Row Margin"]=np.where(x.Sales!=0,x["Gross Profit"]/x.Sales,np.nan); x["Cost Ratio"]=np.where(x.Sales!=0,x.Cost/x.Sales,np.nan)
    c1,c2=st.columns(2)
    with c1:
        fig=px.scatter(x,x="Sales",y="Cost",color="Division" if "Division" in x else None,hover_data=[c for c in ["Product Name","Order Date","Gross Profit"] if c in x],height=390)
        fig.update_layout(margin=dict(l=10,r=10,t=20,b=10),xaxis_title="Sales (USD)",yaxis_title="Cost (USD)")
        st.plotly_chart(fig,use_container_width=True)
    with c2:
        if "Product Name" in x:
            p=aggregate(x,["Product Name"]); p["Cost Ratio"]=np.where(p.Revenue!=0,p.Cost/p.Revenue,np.nan)
            fig=px.bar(p.sort_values("Cost Ratio"),x="Cost Ratio",y="Product Name",orientation="h",height=390)
            fig.update_layout(margin=dict(l=10,r=10,t=20,b=10),xaxis_tickformat=".0%",xaxis_title="Weighted cost / revenue",yaxis_title="")
            st.plotly_chart(fig,use_container_width=True)
    if "Product Name" in x:
        p=aggregate(x,["Product Name"])
        p["Review Prompt"]=np.select([
            p["Weighted Margin"]<rules["low_margin"],
            p["Weighted Margin"]>=rules["low_margin"],
        ],["Review pricing / sourcing / portfolio fit","No margin flag under current rule"],default="N/A")
        st.dataframe(p[[c for c in ["Product Name","Revenue","Cost","Gross Profit","Weighted Margin","Profit / Unit","Review Prompt"] if c in p]],use_container_width=True,hide_index=True,column_config={"Revenue":st.column_config.NumberColumn(format="$%.2f"),"Cost":st.column_config.NumberColumn(format="$%.2f"),"Gross Profit":st.column_config.NumberColumn(format="$%.2f"),"Weighted Margin":st.column_config.NumberColumn(format="%.1%"),"Profit / Unit":st.column_config.NumberColumn(format="$%.2f")})
    with st.expander("Data-quality diagnostics",expanded=False):
        st.json(dq)


def pareto_chart(p, metric, title):
    p=p[["Product Name",metric]].dropna().copy().sort_values(metric,ascending=False)
    total=p[metric].sum()
    if len(p)==0 or total<=0:
        st.warning(f"Pareto unavailable for {metric}: the total is not positive, so cumulative contribution would be misleading.")
        return
    p["Cumulative Share"]=p[metric].cumsum()/total
    fig=go.Figure()
    fig.add_trace(go.Bar(x=p["Product Name"],y=p[metric],name=metric))
    fig.add_trace(go.Scatter(x=p["Product Name"],y=p["Cumulative Share"]*total,name="Cumulative share",mode="lines+markers",yaxis="y2"))
    idx=np.argmax(p["Cumulative Share"].values>=.8) if (p["Cumulative Share"]>=.8).any() else None
    if idx is not None:
        n=idx+1
        fig.add_vline(x=idx,line_dash="dot",annotation_text=f"80% at {n} products")
    fig.update_layout(title=title,height=400,margin=dict(l=10,r=10,t=45,b=100),xaxis_tickangle=-40,yaxis_title="USD",yaxis2=dict(overlaying="y",side="right",tickformat=".0%",title="Cumulative share"),legend=dict(orientation="h"))
    st.plotly_chart(fig,use_container_width=True)
    if idx is not None:
        st.caption(f"80% threshold reached by {idx+1} of {len(p)} products ({(idx+1)/len(p):.1%} of products). Sorting is descending by {metric}.")


def concentration_page(df, rules):
    render_header("Profit Concentration", "Measure how concentrated filtered revenue and gross profit are among products. Pareto views are shown only when the relevant total is positive.")
    if "Product Name" not in df.columns: st.info("Product concentration requires Product Name."); return
    p=aggregate(df,["Product Name"])
    c1,c2=st.columns(2)
    with c1: pareto_chart(p,"Revenue","Revenue concentration by product")
    with c2: pareto_chart(p,"Gross Profit","Gross-profit concentration by product")


def geography_page(df, rules):
    render_header("Geographic Analysis", "Customer/order geography by region and state/province. This is not a shipping-route, delivery-reliability or logistics-efficiency analysis.")
    if not available(df,["Sales","Gross Profit"]): st.info("Geographic analysis requires Sales and Gross Profit plus a geography field."); return
    geo_col="State/Province" if "State/Province" in df.columns else ("Region" if "Region" in df.columns else None)
    if geo_col is None: st.info("No supported geography field is available."); return
    g=aggregate(df,[geo_col])
    c1,c2=st.columns(2)
    with c1:
        top=g.sort_values("Revenue",ascending=False).head(20)
        fig=px.bar(top.sort_values("Revenue"),x="Revenue",y=geo_col,orientation="h",height=480)
        fig.update_layout(margin=dict(l=10,r=10,t=20,b=10),xaxis_title="Revenue (USD)",yaxis_title="")
        st.plotly_chart(fig,use_container_width=True)
    with c2:
        top=g.sort_values("Gross Profit",ascending=False).head(20)
        fig=px.bar(top.sort_values("Gross Profit"),x="Gross Profit",y=geo_col,orientation="h",color="Weighted Margin",height=480)
        fig.update_layout(margin=dict(l=10,r=10,t=20,b=10),xaxis_title="Gross profit (USD)",yaxis_title="")
        st.plotly_chart(fig,use_container_width=True)
    st.dataframe(g.sort_values("Revenue",ascending=False),use_container_width=True,hide_index=True,column_config={"Revenue":st.column_config.NumberColumn(format="$%.2f"),"Cost":st.column_config.NumberColumn(format="$%.2f"),"Gross Profit":st.column_config.NumberColumn(format="$%.2f"),"Weighted Margin":st.column_config.NumberColumn(format="%.1%")})


def factory_page(df, rules):
    render_header("Factory Analysis", "A supplied product-to-factory analytical mapping. Coordinates are used only to visualize the supplied mapping; they do not establish verified manufacturing, operational or shipping relationships.")
    if "Product Name" not in df.columns: st.info("Factory analysis requires Product Name."); return
    unique=set(df["Product Name"].dropna().astype(str))
    matched=unique & set(PRODUCT_FACTORY); unmatched=unique-set(PRODUCT_FACTORY)
    if unmatched: st.warning(f"Unmatched products: {', '.join(sorted(unmatched))}. They are not assigned to a factory.")
    p=aggregate(df,["Product Name"]); p["Factory"]=p["Product Name"].map(PRODUCT_FACTORY); p=p[p.Factory.notna()].copy()
    f=aggregate(p,["Factory"]) if False else p.groupby("Factory").agg(Revenue=("Revenue","sum"),Gross_Profit=("Gross Profit","sum"),Units=("Units","sum")).reset_index()
    f["Weighted Margin"]=np.where(f.Revenue!=0,f.Gross_Profit/f.Revenue,np.nan)
    c1,c2=st.columns(2)
    with c1:
        fig=px.bar(f.sort_values("Gross_Profit"),x="Gross_Profit",y="Factory",orientation="h",height=400)
        fig.update_layout(margin=dict(l=10,r=10,t=20,b=10),xaxis_title="Gross profit (USD)",yaxis_title="")
        st.plotly_chart(fig,use_container_width=True)
    with c2:
        rows=[]
        for fac,(lat,lon) in FACTORY_COORDS.items():
            z=f[f.Factory==fac]
            rows.append({"Factory":fac,"Latitude":lat,"Longitude":lon,"Revenue":z.Revenue.sum() if len(z) else 0,"Gross Profit":z.Gross_Profit.sum() if len(z) else 0})
        m=pd.DataFrame(rows)
        fig=px.scatter_geo(m,lat="Latitude",lon="Longitude",size="Revenue",hover_name="Factory",hover_data={"Latitude":False,"Longitude":False,"Revenue":":$,.2f","Gross Profit":":$,.2f"},scope="north america",height=400)
        fig.update_layout(margin=dict(l=0,r=0,t=20,b=0),geo=dict(showland=True))
        st.plotly_chart(fig,use_container_width=True)
    st.dataframe(p[["Product Name","Factory","Revenue","Gross Profit","Weighted Margin","Units"]].sort_values("Gross Profit",ascending=False),use_container_width=True,hide_index=True,column_config={"Revenue":st.column_config.NumberColumn(format="$%.2f"),"Gross Profit":st.column_config.NumberColumn(format="$%.2f"),"Weighted Margin":st.column_config.NumberColumn(format="%.1%")})
    st.caption(f"Exact product-name matches: {len(matched)}/{len(unique)}. No factory assignment is inferred for unmatched names.")


def quality_page(df, dq, source_mapping, file_name, sheet_name):
    render_header("Data Quality & Methodology", "Inspect the source structure, validation checks and the exact field mappings used by the application.")
    cols=st.columns(4)
    for c,(l,v) in zip(cols,[('Rows',integer(len(df))),('Columns',integer(len(df.columns))),('Duplicate rows',integer(dq['duplicate_rows'])),('Invalid order dates',integer(dq['invalid_order_dates']))]):
        with c: metric_card(l,v,"Source / validation result")
    st.markdown('<div class="section-title">Source inventory</div>',unsafe_allow_html=True)
    st.write({"file":file_name,"sheet":sheet_name or "CSV","rows":len(df),"columns":list(df.columns)})
    st.markdown('<div class="section-title">Column mapping</div>',unsafe_allow_html=True)
    mapping_rows=[{"Dashboard field":k,"Source column":v} for k,v in source_mapping.items()]
    st.dataframe(pd.DataFrame(mapping_rows),use_container_width=True,hide_index=True)
    st.markdown('<div class="section-title">Validation checks</div>',unsafe_allow_html=True)
    q=[]
    for k,v in dq.items(): q.append({"Check":k,"Result":v})
    st.dataframe(pd.DataFrame(q),use_container_width=True,hide_index=True)
    if "Order Date" in df.columns:
        st.markdown(f'<div class="flag">Order-date coverage: <b>{df["Order Date"].min():%d %b %Y}</b> to <b>{df["Order Date"].max():%d %b %Y}</b>.</div>',unsafe_allow_html=True)
    if "Ship Date" in df.columns and "Order Date" in df.columns:
        st.markdown(f'<div class="flag">Ship-date integrity warning: observed ship lag is {dq.get("ship_lag_min_days")} to {dq.get("ship_lag_max_days")} days. The inspected source therefore should not be interpreted as normal fulfillment timing without source-system confirmation.</div>',unsafe_allow_html=True)
    st.markdown('<div class="section-title">Current filter data download</div>',unsafe_allow_html=True)
    st.download_button("Download filtered records as CSV",df.to_csv(index=False).encode("utf-8"),file_name="nassau_filtered.csv",mime="text/csv",use_container_width=False)


def main():
    st.sidebar.markdown("## Nassau Candy")
    st.sidebar.caption("Product Line Profitability & Margin Performance")
    upload=st.sidebar.file_uploader("Replace dataset (CSV / Excel)",type=["csv","xlsx","xls"])
    default_path=Path("Nassau Candy Distributor(1).csv")
    if upload is not None:
        file_bytes=upload.getvalue(); file_name=upload.name
    elif default_path.exists():
        file_bytes=default_path.read_bytes(); file_name=default_path.name
    else:
        st.error("Default dataset not found. Upload the Nassau Candy CSV/Excel file from the sidebar.")
        st.stop()
    sheets=read_source(file_bytes,file_name)
    if len(sheets)>1:
        sheet_names=[s for s,_ in sheets]
        chosen=st.sidebar.selectbox("Excel sheet",sheet_names)
        sheet_name=chosen
        raw=dict(sheets)[chosen]
    else: sheet_name,raw=sheets[0]
    df,source_mapping,dq=validate_and_prepare(raw)
    # Minimum margin is a UI filter; keep rows with missing margin visible only when threshold is 0.
    filtered,rules=filters(df)
    if rules["min_margin"]>0 and available(filtered,["Sales","Gross Profit"]):
        m=np.where(filtered["Sales"]!=0,filtered["Gross Profit"]/filtered["Sales"],np.nan)
        filtered=filtered[pd.Series(m,index=filtered.index)>=rules["min_margin"]]
    st.sidebar.caption(f"Active records: {len(filtered):,} / {len(df):,}")
    st.sidebar.divider()
    page=st.sidebar.radio("Navigate",["Executive Overview","Product Profitability","Division Performance","Cost & Margin Diagnostics","Profit Concentration","Geographic Analysis","Factory Analysis","Data Quality & Methodology"],index=0)
    if page=="Executive Overview": overview(filtered,rules)
    elif page=="Product Profitability": product_page(filtered,rules)
    elif page=="Division Performance": division_page(filtered,rules)
    elif page=="Cost & Margin Diagnostics": diagnostics_page(filtered,rules,dq)
    elif page=="Profit Concentration": concentration_page(filtered,rules)
    elif page=="Geographic Analysis": geography_page(filtered,rules)
    elif page=="Factory Analysis": factory_page(filtered,rules)
    else: quality_page(df,dq,source_mapping,file_name,sheet_name)

if __name__ == "__main__":
    main()
