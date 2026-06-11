"""
ADS-B Analytics Dashboard.
Live web dashboard for KDTW flight data.
"""

import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "adsb"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


def fetch_data():
    query = """
        SELECT callsign, icao24, origin_country,
               latitude, longitude, baro_altitude,
               velocity, on_ground, collected_at
        FROM aircraft_states
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY collected_at DESC;
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# Initialize app
app = dash.Dash(__name__)
app.title = "ADS-B Analytics — KDTW"

app.layout = html.Div(style={
    "backgroundColor": "#0d1117",
    "color": "#e6edf3",
    "fontFamily": "monospace",
    "padding": "20px"
}, children=[

    # Header
    html.Div([
        html.H1("✈ ADS-B Analytics Platform",
                style={"color": "#58a6ff", "marginBottom": "4px"}),
        html.P("Detroit Metro Airport (KDTW) — Live Flight Data",
               style={"color": "#8b949e", "marginTop": "0px"}),
    ]),

    # Refresh interval
    dcc.Interval(id="interval", interval=60 * 1000, n_intervals=0),

    # Stats row
    html.Div(id="stats-row", style={
        "display": "flex", "gap": "20px", "marginBottom": "20px"
    }),

    # Charts row
    html.Div([
        html.Div([
            dcc.Graph(id="hourly-chart")
        ], style={"flex": "1"}),

        html.Div([
            dcc.Graph(id="altitude-chart")
        ], style={"flex": "1"}),
    ], style={"display": "flex", "gap": "20px", "marginBottom": "20px"}),

    # Map
    html.Div([
        dcc.Graph(id="flight-map")
    ], style={"marginBottom": "20px"}),

    # Top aircraft table
    html.Div([
        html.H3("Most Frequent Aircraft",
                style={"color": "#58a6ff"}),
        html.Div(id="top-aircraft-table")
    ])
])


def stat_card(title, value, color="#58a6ff"):
    return html.Div([
        html.P(title, style={"color": "#8b949e", "margin": "0",
                              "fontSize": "12px"}),
        html.H2(value, style={"color": color, "margin": "4px 0"})
    ], style={
        "backgroundColor": "#161b22",
        "border": "1px solid #30363d",
        "borderRadius": "8px",
        "padding": "16px",
        "flex": "1",
        "textAlign": "center"
    })


@app.callback(
    Output("stats-row", "children"),
    Output("hourly-chart", "figure"),
    Output("altitude-chart", "figure"),
    Output("flight-map", "figure"),
    Output("top-aircraft-table", "children"),
    Input("interval", "n_intervals")
)
def update_dashboard(n):
    df = fetch_data()

    # --- Stats ---
    total = len(df)
    unique = df["icao24"].nunique()
    airborne = len(df[df["on_ground"] == False])
    countries = df["origin_country"].nunique()

    stats = html.Div([
        stat_card("Total Records", f"{total:,}"),
        stat_card("Unique Aircraft", f"{unique:,}", "#3fb950"),
        stat_card("Airborne Records", f"{airborne:,}", "#d29922"),
        stat_card("Countries", f"{countries:,}", "#f78166"),
    ], style={"display": "flex", "gap": "20px", "width": "100%"})

    # --- Hourly chart ---
    df["hour"] = pd.to_datetime(df["collected_at"]).dt.hour
    hourly = df.groupby("hour")["icao24"].nunique().reset_index()
    hourly.columns = ["hour", "aircraft"]

    hourly_fig = px.bar(
        hourly, x="hour", y="aircraft",
        title="Unique Aircraft by Hour of Day",
        labels={"hour": "Hour", "aircraft": "Aircraft Count"},
        color="aircraft",
        color_continuous_scale="Blues"
    )
    hourly_fig.update_layout(
        plot_bgcolor="#161b22",
        paper_bgcolor="#161b22",
        font_color="#e6edf3",
        showlegend=False
    )

    # --- Altitude distribution ---
    airborne_df = df[(df["on_ground"] == False) &
                     (df["baro_altitude"].notna()) &
                     (df["baro_altitude"] < 15000)]

    alt_fig = px.histogram(
        airborne_df, x="baro_altitude",
        nbins=40,
        title="Altitude Distribution (Airborne Aircraft)",
        labels={"baro_altitude": "Altitude (m)"},
        color_discrete_sequence=["#58a6ff"]
    )
    alt_fig.update_layout(
        plot_bgcolor="#161b22",
        paper_bgcolor="#161b22",
        font_color="#e6edf3"
    )

    # --- Flight map ---
    latest = df.sort_values("collected_at").groupby("icao24").last().reset_index()
    latest = latest[latest["latitude"].notna() & latest["longitude"].notna()]

    map_fig = go.Figure(go.Scattermapbox(
        lat=latest["latitude"],
        lon=latest["longitude"],
        mode="markers",
        marker=dict(size=8, color="#58a6ff", opacity=0.8),
        text=latest["callsign"],
        hovertemplate="<b>%{text}</b><br>Lat: %{lat}<br>Lon: %{lon}<extra></extra>"
    ))

    map_fig.add_trace(go.Scattermapbox(
        lat=[42.2124],
        lon=[-83.3534],
        mode="markers+text",
        marker=dict(size=14, color="#f78166"),
        text=["KDTW"],
        textposition="top right",
        textfont=dict(color="#f78166", size=12)
    ))

    map_fig.update_layout(
        mapbox=dict(
            style="carto-darkmatter",
            center=dict(lat=42.2124, lon=-83.3534),
            zoom=7
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=500,
        title="Latest Aircraft Positions",
        paper_bgcolor="#161b22",
        font_color="#e6edf3"
    )

    # --- Top aircraft table ---
    top = (df[df["callsign"].notna()]
           .groupby("callsign")["icao24"]
           .count()
           .reset_index()
           .rename(columns={"icao24": "appearances"})
           .sort_values("appearances", ascending=False)
           .head(10))

    table = html.Table([
        html.Thead(html.Tr([
            html.Th("Callsign", style={"padding": "8px 16px",
                                        "color": "#8b949e"}),
            html.Th("Appearances", style={"padding": "8px 16px",
                                           "color": "#8b949e"})
        ])),
        html.Tbody([
            html.Tr([
                html.Td(row["callsign"],
                        style={"padding": "8px 16px", "color": "#58a6ff"}),
                html.Td(row["appearances"],
                        style={"padding": "8px 16px"})
            ]) for _, row in top.iterrows()
        ])
    ], style={
        "backgroundColor": "#161b22",
        "border": "1px solid #30363d",
        "borderRadius": "8px",
        "width": "100%"
    })

    return stats, hourly_fig, alt_fig, map_fig, table


if __name__ == "__main__":
    app.run(debug=True)