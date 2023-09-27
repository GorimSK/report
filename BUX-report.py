import streamlit as st
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import time
import plotly.express as px

# Set the page config at the top of your script
st.set_page_config(page_title="Data Reports", page_icon="📊")

# Custom CSS for thicker progress bar
st.markdown("""
<style>
    .stProgress > div > div > div {
        height: 25px;   /* Adjust the height value for desired thickness */
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def fetch_data_from_worksheet(worksheet_name):
    credentials_file_path = "budget-report-keys.json"
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file_path, scope)
    client = gspread.authorize(creds)

    sheet = client.open("BUX-DATA").worksheet(worksheet_name)
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    df['Date'] = pd.to_datetime(df['Date'])

    # Strip out the '€' character and any possible whitespace
    df['Total Revenue'] = df['Total Revenue'].str.replace('€', '').str.strip()
    # Convert the cleaned data to float
    df['Total Revenue'] = df['Total Revenue'].astype(float)
    return df



def get_current_month_data(df):
    today = datetime.date.today()
    current_month = today.month
    current_year = today.year
    current_month_df = df[(df['Date'].dt.month == current_month) & (df['Date'].dt.year == current_year)]
    return current_month_df


def revenue_data_page():
    df = fetch_data_from_worksheet("Report")

    st.sidebar.title("Filters")

    # Get the first and last day of the current month
    first_day_of_month = datetime.date.today().replace(day=1)
    computed_last_day_of_month = datetime.date.today().replace(month=datetime.date.today().month + 1,
                                                               day=1) - datetime.timedelta(days=1)
    last_day_of_month = min(computed_last_day_of_month, df['Date'].max().date())

    start_date = st.sidebar.date_input("Start Date", first_day_of_month, min_value=df['Date'].min().date(),
                                       max_value=df['Date'].max().date())
    end_date = st.sidebar.date_input("End Date", last_day_of_month, min_value=start_date,
                                     max_value=df['Date'].max().date())

    # Filter the dataframe for the dates provided in sidebar
    date_filtered_df = df[(df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)]

    source_medium_defaults = ["google / cpc", "google / organic", "(not set)", "facebook / cpc"]
    available_mediums = date_filtered_df["Source/Medium"].unique().tolist()
    source_medium_selected = [medium for medium in source_medium_defaults if medium in available_mediums]
    source_mediums = st.sidebar.multiselect("Source/Medium", options=available_mediums, default=source_medium_selected)

    # Filter by selected source/mediums
    filtered_df = date_filtered_df[date_filtered_df["Source/Medium"].isin(source_mediums)]

    # Now create a new dataframe with summed metrics for the current month by 'Source/Medium'
    current_month_summed_df = filtered_df.groupby("Source/Medium").agg({"Total Revenue": "sum"}).reset_index()
    current_month_summed_df['Total Revenue'] = '€ ' + current_month_summed_df['Total Revenue'].astype(float).round(
        2).astype(str)

    st.markdown("<h2 style='font-size: 20px;'>Všeobecný prehľad (Current Month)</h2>", unsafe_allow_html=True)
    st.dataframe(current_month_summed_df, use_container_width=True)

    # Display the line graph
    st.markdown("<h2 style='font-size: 20px;'>Vývoj výnosov</h2>", unsafe_allow_html=True)
    chart_data = filtered_df.groupby(['Date', 'Source/Medium']).agg({'Total Revenue': 'sum'}).reset_index()
    fig = px.line(chart_data, x='Date', y='Total Revenue', color='Source/Medium', markers=True,
                  labels={'Total Revenue': 'Total Revenue €'})

    for _, row in chart_data.iterrows():
        fig.add_annotation(x=row['Date'], y=row['Total Revenue'], text=f"€ {row['Total Revenue']:.2f}", showarrow=False,
                           yshift=10)

    st.plotly_chart(fig)

    # Display the summarized total revenue as a score card (filtered only by date)
    date_filtered_revenue = df[(df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)][
        "Total Revenue"].sum()
    st.markdown(f"""
    <div style="background-color: #f2f2f2; padding: 20px; border-radius: 10px;">
        <h2 style="text-align: center; font-size: 22px;">Výnosy celkom</h2>
        <h1 style="text-align: center; font-size: 22px;">{date_filtered_revenue:,.2f} €</h1>
    </div>
    """, unsafe_allow_html=True)

    # Display the source dataframe (filtered_df)
    st.markdown("<h2 style='font-size: 20px;'>Source Dataframe</h2>", unsafe_allow_html=True)
    st.dataframe(filtered_df, use_container_width=True)


def google_ads_report_page():
    df = fetch_data_from_worksheet("Google_Ads_Report")

    # Convert the 'Date' column to a simple date format
    df['Date'] = df['Date'].dt.date

    st.sidebar.title("Date Filters")

    # Using date filters
    first_day_of_month = datetime.date.today().replace(day=1)
    computed_last_day_of_month = datetime.date.today().replace(month=datetime.date.today().month + 1,
                                                               day=1) - datetime.timedelta(days=1)
    last_day_of_month = min(computed_last_day_of_month, df['Date'].max())

    start_date = st.sidebar.date_input("Start Date", first_day_of_month, min_value=df['Date'].min(),
                                       max_value=df['Date'].max())
    end_date = st.sidebar.date_input("End Date", last_day_of_month, min_value=start_date, max_value=df['Date'].max())

    filtered_df = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
    filtered_df = filtered_df[~filtered_df['Campaign Name'].str.contains("(not set)|(direct)", na=False)]
    filtered_df['Ad Cost'] = pd.to_numeric(filtered_df['Ad Cost'], errors='coerce')

    st.markdown("<h2 style='font-size: 20px;'>Google Ads Kampane</h2>", unsafe_allow_html=True)
    df_summed_campaign = filtered_df.groupby('Campaign Name').agg({'Total Revenue': 'sum'}).reset_index()
    st.dataframe(df_summed_campaign, use_container_width=True)

    # Bar graph for the summed data by Campaign
    fig = px.bar(df_summed_campaign, x='Campaign Name', y='Total Revenue', labels={'Total Revenue': '€ Total Revenue'},
                 title="Total Revenue by Campaign")

    for _, row in df_summed_campaign.iterrows():
        fig.add_annotation(x=row['Campaign Name'], y=row['Total Revenue'], text=f"€ {row['Total Revenue']:.2f}",
                           showarrow=False, yshift=10)
    st.plotly_chart(fig, use_container_width=True)

    # Animated Line graph to show Ad Cost progression in the current month
    df_summed_ad_cost = filtered_df.groupby('Date').agg({'Ad Cost': 'sum'}).reset_index()
    line_chart_placeholder = st.empty()

    dates = df_summed_ad_cost['Date'].tolist()
    for end_date_index, end_date in enumerate(dates):
        temp_df = df_summed_ad_cost.iloc[:end_date_index + 1]
        fig_ad_cost_temp = px.line(temp_df, x='Date', y='Ad Cost', labels={'Ad Cost': '€ Ad Cost'}, markers=True,
                                   title="Ad Cost Over Time")

        for _, row in temp_df.iterrows():
            fig_ad_cost_temp.add_annotation(x=row['Date'], y=row['Ad Cost'], text=f"€ {row['Ad Cost']:.2f}",
                                            showarrow=False, yshift=10)

        line_chart_placeholder.plotly_chart(fig_ad_cost_temp, use_container_width=True)
        time.sleep(0.2)

    # Calculate total Ad Cost for the filtered data and display it as a score card
    total_ad_cost = filtered_df['Ad Cost'].sum()
    st.markdown(f"<h2 style='font-size: 20px;'>Celkové náklady: {total_ad_cost:.2f} €</h2>", unsafe_allow_html=True)

    # Animated Progress bar for Ad Cost
    threshold = 3000
    progress_bar = st.empty()
    for i in range(0, int(total_ad_cost) + 1):
        time.sleep(0.01)
        progress_ratio = i / threshold
        progress_bar.progress(progress_ratio)
    st.write(f"Celkový rozpočet {threshold:.2f} €")


page = st.sidebar.radio(
    "Choose a page",
    ["🌐Revenue Data", "🔍Google Ads Report"]
)


if page == "🌐Revenue Data":
    revenue_data_page()
elif page == "🔍Google Ads Report":
    google_ads_report_page()
