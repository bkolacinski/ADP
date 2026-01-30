import folium
import geopandas as gpd
import pandas as pd
from branca.colormap import LinearColormap


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
        .rename(columns={"Incident.year": "year",
                         "Incident.month": "month"})
        .assign(day=1),
        errors="coerce",
    )

    df["is_fatal"] = df["Injury.severity"].apply(
        lambda x: 1 if str(x).lower() == "fatal" else 0
    )

    df = df.dropna(subset=["lat", "long"])

    df = df[df["Incident.year"] >= 2015]

    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df.long, df.lat),
        crs="EPSG:4326"
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
        df, geometry=gpd.points_from_xy(df.long, df.lat),
        crs="EPSG:4326"
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


def read_population_data(path: str) -> gpd.GeoDataFrame:
    df = pd.read_csv(path)
    pop_density_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(
        df.x, df.y))
    pop_density_gdf = pop_density_gdf.to_crs("EPSG:4326")
    return pop_density_gdf


# python
def create_map(
        gdf: gpd.GeoDataFrame, pop_gdf: gpd.GeoDataFrame, output_file:
        str = "croc_map.html"
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
    fg_shark_non_fatal = folium.FeatureGroup(
        name="Shark Attacks: Non-fatal")

    fg_population = folium.FeatureGroup(name="Population Density")

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

    if pop_gdf is not None and len(pop_gdf) > 0:
        pop = pop_gdf.copy()

        if pop.crs is None:
            pop = pop.set_crs("EPSG:4326", allow_override=True)
        else:
            pop = pop.to_crs("EPSG:4326")

        possible_names = [
            "population_density", "pop_density", "population",
            "pop", "density", "value"
        ]
        numeric_cols = pop.select_dtypes(include=["number"]).columns.tolist()
        field = next((n for n in possible_names if n in pop.columns), None)
        if field is None and numeric_cols:
            field = numeric_cols[0]

        if field is not None:
            vals = pop[field].dropna()
            if len(vals) > 0:
                vmin = float(vals.min())
                vmax = float(vals.max())
            else:
                vmin, vmax = 0.0, 1.0

            if vmin == vmax:
                vmax = vmin + 1.0

            cmap = LinearColormap(
                ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
                vmin=vmin, vmax=vmax,
                caption="Population density"
            )

            geom_types = set(pop.geometry.geom_type)
            # poprawione rozpoznawanie poligonów (obsługuje MultiPolygon)
            if any("polygon" in gt.lower() for gt in geom_types):
                def style_function(feature):
                    val = feature["properties"].get(field, None)
                    try:
                        color = cmap(float(val)) if val is not None else "#ffffff00"
                        fill_opacity = 0.7 if val is not None else 0.0
                    except Exception:
                        color = "#ffffff00"
                        fill_opacity = 0.0
                    return {
                        "fillColor": color,
                        "color": "black",
                        "weight": 0.3,
                        "fillOpacity": fill_opacity,
                    }

                folium.GeoJson(
                    pop.to_json(),
                    style_function=style_function,
                    name="Population Density (choropleth)",
                ).add_to(fg_population)
            else:
                for _, prow in pop.iterrows():
                    val = prow.get(field, None)
                    if pd.notna(val) and prow.geometry is not None:
                        try:
                            fval = float(val)
                        except Exception:
                            continue
                        # użyj centroidu jako punktu reprezentatywnego (działa też dla Multi*)
                        centroid = prow.geometry.centroid
                        # normalizacja promienia
                        radius = max(2, (fval - vmin) / (vmax - vmin) * 18 + 2)
                        folium.CircleMarker(
                            location=[centroid.y, centroid.x],
                            radius=radius,
                            fill=True,
                            fill_color=cmap(fval),
                            color=None,
                            fill_opacity=0.7,
                            popup=folium.Popup(f"{field}: {fval}", max_width=200),
                        ).add_to(fg_population)

            # dodaj legendę/kolorystykę raz do mapy
            cmap.add_to(m)

    fg_croc_fatal.add_to(m)
    fg_croc_non_fatal.add_to(m)
    fg_shark_fatal.add_to(m)
    fg_shark_non_fatal.add_to(m)
    fg_population.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(output_file)


if __name__ == "__main__":
    data_croc = read_croc_data("../data/croc_attacks.csv")
    data_shark = read_shark_data("../data/shark_attacks.xlsx")
    pop_density_gdf = gpd.read_file("../data/population_density.gpkg")

    data_combined = gpd.GeoDataFrame(
        pd.concat([data_croc, data_shark], ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )

    create_map(data_combined, pop_density_gdf, output_file="map.html")
