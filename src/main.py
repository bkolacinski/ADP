import folium
import geopandas as gpd
import pandas as pd


def read_shark_data(path: str) -> gpd.GeoDataFrame:
    df = pd.read_excel(path)

    columns = [
        "Latitude",
        "Longitude",
        "Injury.severity",
        "Victim.gender",
        "Incident.month",
        "Incident.year",
        "Shark.common.name",
        "Victim.activity",
        "Provoked/unprovoked",
    ]

    df = df[columns].copy()

    df = df.rename(
        columns={
            "Latitude": "lat",
            "Longitude": "long",
            "Victim.gender": "sex",
            "Shark.common.name": "species",
            "Victim.activity": "activity",
            "Provoked/unprovoked": "provoked",
        }
    )

    df["date"] = pd.to_datetime(
        df[["Incident.year", "Incident.month"]]
        .rename(columns={"Incident.year": "year", "Incident.month": "month"})
        .assign(day=1),
        errors="coerce",
    )

    df["is_fatal"] = df["Injury.severity"].apply(
        lambda x: 1 if str(x).lower() == "fatal" else 0
    )

    df = df.dropna(subset=["lat", "long"])

    df = df[df["Incident.year"] >= 2015]

    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df.long, df.lat), crs="EPSG:4326"
    )

    gdf = gpd.GeoDataFrame(
        gdf[
            [
                "geometry",
                "lat",
                "long",
                "is_fatal",
                "sex",
                "date",
                "species",
                "activity",
                "provoked",
            ]
        ].copy()
    )

    return gdf


def read_croc_data(path: str) -> gpd.GeoDataFrame:
    df = pd.read_csv(path)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df.long, df.lat), crs="EPSG:4326"
    )

    gdf["species"] = "crocodile"
    gdf["activity"] = None
    gdf["provoked"] = None

    gdf = gpd.GeoDataFrame(
        gdf[
            [
                "geometry",
                "lat",
                "long",
                "is_fatal",
                "sex",
                "date",
                "species",
                "activity",
                "provoked",
            ]
        ].copy()
    )

    return gdf


def create_map(
    gdf: gpd.GeoDataFrame, output_file: str = "croc_map.html"
) -> None:
    m = folium.Map(
        location=[-25.2744, 133.7751],
        zoom_start=4,
        tiles="cartodbpositron",
    )

    fg_croc_fatal = folium.FeatureGroup(name="Crocodile Attacks: Fatal")
    fg_croc_non_fatal = folium.FeatureGroup(
        name="Crocodile Attacks: Non-fatal"
    )

    fg_shark_fatal = folium.FeatureGroup(name="Shark Attacks: Fatal")
    fg_shark_non_fatal = folium.FeatureGroup(name="Shark Attacks: Non-fatal")

    fg_population = folium.FeatureGroup(name="Population Density (NIE MA)")

    croc_icon_path = "icons/crocodile.png"
    shark_icon_path = "icons/shark.png"

    for _, row in gdf.iterrows():
        popup_info = ""
        for col in gdf.columns:
            if col != "geometry":
                value = row[col]
                if pd.notna(value) and value != "" and value is not None:
                    popup_info += f"<b>{col}:</b> {value}<br>"

        is_shark = "shark" in str(row.get("species", "")).lower()
        icon_path = shark_icon_path if is_shark else croc_icon_path

        if row["is_fatal"] == 1:
            bg_color = "#d32f2f"
            target_group = fg_shark_fatal if is_shark else fg_croc_fatal
        else:
            bg_color = "#f57c00"
            target_group = (
                fg_shark_non_fatal if is_shark else fg_croc_non_fatal
            )

        icon_size_px = (16, 16)
        icon_html = f"""
                    <div style="
                        background-color: {bg_color};
                        border-radius: 50%;
                        width: {int(icon_size_px[0] * 1.5)}px;
                        height: {int(icon_size_px[1] * 1.5)}px;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        border: 2px solid white;
                        box-shadow: 0 0 5px rgba(0,0,0,0.5);
                    ">
                        <img src="{icon_path}" style="width: {icon_size_px[0]}px; height: {icon_size_px[1]}px;">
                    </div>
                """

        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup_info, max_width=300),
            icon=folium.DivIcon(
                html=icon_html, icon_size=(16, 16), icon_anchor=(8, 8)
            ),
        ).add_to(target_group)

    fg_croc_fatal.add_to(m)
    fg_croc_non_fatal.add_to(m)
    fg_shark_fatal.add_to(m)
    fg_shark_non_fatal.add_to(m)
    fg_population.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(output_file)


if __name__ == "__main__":
    data_croc = read_croc_data("data/croc_attacks.csv")
    data_shark = read_shark_data("data/shark_attacks.xlsx")

    data_combined = gpd.GeoDataFrame(
        pd.concat([data_croc, data_shark], ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )

    create_map(data_combined)
