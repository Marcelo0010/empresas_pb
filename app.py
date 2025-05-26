import pandas as pd
import geopandas as gpd
from geobr import read_municipality
import plotly.express as px
from dash import Dash, dcc, html, Input, Output
import unicodedata
import json

# === Lê base (coloque o caminho correto ou carregue arquivo na nuvem) ===
df = pd.read_excel('base.xlsx')  # arquivo base.xlsx deve estar na raiz do projeto

fixas = ['IBGE Gr Setor', 'CNAE 2.0 Subclasse']
col_municipios = [col for col in df.columns if col not in fixas]

df_long = df.melt(id_vars=fixas, value_vars=col_municipios,
                  var_name='Municipio', value_name='Valor')
df_long = df_long[df_long['Valor'] > 0]

df_long['Municipio'] = (
    df_long['Municipio']
    .str.replace(r'^Pb-', '', regex=True)
    .str.replace(r'\.1$', '', regex=True)
    .apply(lambda x: unicodedata.normalize('NFKD', x).encode('ascii', errors='ignore').decode('utf-8').lower())
)

gdf_pb = read_municipality(code_muni='PB', year=2022)
gdf_pb['name_muni'] = gdf_pb['name_muni'].apply(
    lambda x: unicodedata.normalize('NFKD', x).encode('ascii', errors='ignore').decode('utf-8').lower()
)

app = Dash(__name__)

app.layout = html.Div([
    html.H1("Mapa Interativo de Atividades Econômicas na Paraíba"),

    html.Label("Filtrar por Setor:"),
    dcc.Dropdown(
        id='setor-dropdown',
        options=[{'label': s, 'value': s} for s in df_long['IBGE Gr Setor'].unique()],
        value=df_long['IBGE Gr Setor'].unique()[0]
    ),

    html.Label("Filtrar por Subclasse:"),
    dcc.Dropdown(id='subclasse-dropdown'),

    dcc.Graph(id='mapa-paraiba')
])

@app.callback(
    Output('subclasse-dropdown', 'options'),
    Output('subclasse-dropdown', 'value'),
    Input('setor-dropdown', 'value')
)
def atualizar_subclasse(setor):
    opcoes = df_long[df_long['IBGE Gr Setor'] == setor]['CNAE 2.0 Subclasse'].unique()
    return [{'label': c, 'value': c} for c in opcoes], opcoes[0]

@app.callback(
    Output('mapa-paraiba', 'figure'),
    Input('setor-dropdown', 'value'),
    Input('subclasse-dropdown', 'value')
)
def atualizar_mapa(setor, subclasse):
    dados = df_long[
        (df_long['IBGE Gr Setor'] == setor) & 
        (df_long['CNAE 2.0 Subclasse'] == subclasse)
    ]

    merged = gdf_pb.merge(dados, left_on='name_muni', right_on='Municipio', how='left')
    merged['Valor'] = merged['Valor'].fillna(0)

    # Criar um ID para geojson para evitar problemas
    merged = merged.reset_index(drop=True)
    merged['id'] = merged.index.astype(str)
    geojson_dict = json.loads(merged.to_json())

    fig = px.choropleth_mapbox(
        merged,
        geojson=geojson_dict,
        locations='id',
        color='Valor',
        hover_name='name_muni',
        mapbox_style='carto-positron',
        center={"lat": -7.24, "lon": -36.78},
        zoom=6.3,
        opacity=0.6
    )
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return fig

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
