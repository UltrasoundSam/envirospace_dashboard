"""Streamlit dashboard for stored EnviroSpace readings."""

import logging
from datetime import date, timedelta

import pandas as pd
import pymysql
import streamlit as st

from envirospace_dashboard.database import (
    connect_to_db,
    get_device_ids,
    get_readings,
)
from envirospace_dashboard.ingestion.settings import DatabaseSettings

logger = logging.getLogger(__name__)

READING_COLUMNS = (
    "recorded_at",
    "temperature",
    "humidity",
    "noise",
    "light_lux",
    "pressure",
)
MEASUREMENTS = {
    "temperature": ("Temperature", "°C"),
    "humidity": ("Humidity", "%"),
    "noise": ("Noise", ""),
    "light_lux": ("Light", "lux"),
    "pressure": ("Pressure", "hPa"),
}


def main() -> None:
    st.set_page_config(page_title="EnviroSpace", layout="wide")
    st.title("EnviroSpace")
    st.caption("Environmental readings by device")

    try:
        settings = DatabaseSettings.from_env()
    except (OSError, ValueError) as error:
        st.error(f"Database configuration is incomplete: {error}")
        st.stop()

    connection = connect_to_db(settings)
    if connection is None:
        msg = "Could not connect to the database. Check the database settings."
        st.error(msg)
        st.stop()

    try:
        device_ids = get_device_ids(connection)
        if not device_ids:
            st.info("No readings are available yet.")
            st.stop()

        with st.sidebar:
            st.header("Filters")
            device_id = st.selectbox("Device", device_ids)
            end_date = st.date_input("To", value=date.today())
            start_date = st.date_input(
                "From",
                value=end_date - timedelta(days=7),
            )

        if start_date > end_date:
            st.error("The start date must be on or before the end date.")
            st.stop()

        readings = get_readings(connection, device_id, start_date, end_date)
    except pymysql.Error:
        logger.exception("Could not load dashboard readings")
        st.error("Could not load readings from the database.")
        st.stop()
    finally:
        connection.close()

    if not readings:
        st.info("No readings found for this device and date range.")
        return

    frame = pd.DataFrame(readings, columns=READING_COLUMNS)
    frame["recorded_at"] = pd.to_datetime(frame["recorded_at"])
    for measurement in MEASUREMENTS:
        frame[measurement] = pd.to_numeric(frame[measurement], errors="coerce")

    latest = frame.iloc[-1]
    metric_columns = st.columns(len(MEASUREMENTS))
    for column, (measurement, (label, unit)) in zip(
        metric_columns,
        MEASUREMENTS.items(),
    ):
        value = latest[measurement]
        formatted_value = "—" if pd.isna(value) else f"{value:.1f} {unit}".strip()
        column.metric(label, formatted_value)

    st.caption(f"Latest reading: {latest['recorded_at']:%Y-%m-%d %H:%M}")

    selected_measurement = st.selectbox(
        "Trend",
        options=list(MEASUREMENTS),
        format_func=lambda key: MEASUREMENTS[key][0],
    )
    measurement_label, unit = MEASUREMENTS[selected_measurement]
    st.line_chart(
        frame,
        x="recorded_at",
        y=selected_measurement,
        y_label=f"{measurement_label} ({unit})" if unit else measurement_label,
    )

    st.subheader("Readings")
    st.dataframe(frame, hide_index=True, width="stretch")


if __name__ == "__main__":
    main()
