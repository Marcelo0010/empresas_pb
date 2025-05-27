import pandas as pd
import geopandas as gpd
from geobr import read_municipality
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc

# === LEITURA DA BASE ===
df = pd.read_excel('base.xlsx')  # Substitua pelo caminho correto se necessário

# === TRANSFORMAÇÃO PARA FORMATO LONGO ===
fixas = ['IBGE Gr Setor', 'CNAE 2.0 Subclasse']
col_municipios = [col for col in df.columns if col not in fixas]

df_long = df.melt(id_vars=fixas, value_vars=col_municipios, 
                  var_name='Municipio', value_name='Empresas')

# Filtra valores positivos
df_long = df_long[df_long['Empresas'] > 0]

# Padroniza nomes de municípios
df_long['Municipio'] = (
    df_long['Municipio']
    .str.replace(r'^Pb-', '', regex=True)
    .str.replace(r'\.1$', '', regex=True)
    .str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
    .str.lower()
)

# === GEODADOS ===
gdf_pb = read_municipality(code_muni='PB', year=2022)
gdf_pb['Municipio_merge'] = gdf_pb['name_muni'].str.lower()

# === DASH ===
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Empresas por Município - PB"

# === LAYOUT ===
app.layout = dbc.Container([
    html.H2("📍 Mapa de Empresas por Município na Paraíba - 2024", className="my-4 text-center"),

    dbc.Row([
        dbc.Col([
            html.Label("Filtrar por Setor:"),
            dcc.Dropdown(
                id='setor-dropdown',
                options=[{'label': s, 'value': s} for s in df_long['IBGE Gr Setor'].unique()],
                value=df_long['IBGE Gr Setor'].unique()[0],
                clearable=False
            )
        ], md=6),

        dbc.Col([
            html.Label("Filtrar por Subclasse (CNAE):"),
            dcc.Dropdown(id='subclasse-dropdown', clearable=False)
        ], md=6)
    ], className="mb-4"),

    dcc.Tabs(id='tabs', value='mapa', children=[
        dcc.Tab(label='🗺️ Mapa Interativo', value='mapa'),
        dcc.Tab(label='📊 Tabela por Município', value='tabela'),
        dcc.Tab(label='🏆 Top 10 Municípios', value='top'),
        dcc.Tab(label='📈 Análises Complementares', value='analises')
    ]),

    html.Div(id='conteudo-tab', className="mt-4"),

    html.Hr(),
    html.Footer("Elaborado por Marcelo Martins - Sindalcool", className="text-center text-muted mb-4")
], fluid=True)

# === CALLBACK PARA SUBCLASSES ===
@app.callback(
    Output('subclasse-dropdown', 'options'),
    Output('subclasse-dropdown', 'value'),
    Input('setor-dropdown', 'value')
)
def atualizar_subclasse(setor):
    opcoes = df_long[df_long['IBGE Gr Setor'] == setor]['CNAE 2.0 Subclasse'].unique()
    return [{'label': c, 'value': c} for c in opcoes], opcoes[0]

# === CALLBACK PARA CONTEÚDO ===
@app.callback(
    Output('conteudo-tab', 'children'),
    Input('tabs', 'value'),
    Input('setor-dropdown', 'value'),
    Input('subclasse-dropdown', 'value')
)
def atualizar_conteudo(tab, setor, subclasse):
    dados = df_long[
        (df_long['IBGE Gr Setor'] == setor) &
        (df_long['CNAE 2.0 Subclasse'] == subclasse)
    ]
    merged = gdf_pb.merge(dados, left_on='Municipio_merge', right_on='Municipio', how='left')
    merged['Empresas'] = merged['Empresas'].fillna(0)

    if tab == 'mapa':
        fig = px.choropleth_mapbox(
            merged,
            geojson=merged.geometry,
            locations=merged.index,
            color='Empresas',
            hover_name='name_muni',
            mapbox_style='carto-positron',
            center={"lat": -7.24, "lon": -36.78},
            zoom=6.3,
            opacity=0.6,
            color_continuous_scale='YlGnBu',
            labels={'Empresas': 'Empresas'}
        )
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        return dcc.Graph(figure=fig)

    elif tab == 'tabela':
        tabela = merged[['name_muni', 'Empresas']].rename(columns={
            'name_muni': 'Município',
            'Empresas': 'Qtde de Empresas'
        }).sort_values(by='Município')

        return dash_table.DataTable(
            columns=[{"name": i, "id": i} for i in tabela.columns],
            data=tabela.to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'left', 'padding': '5px'},
            style_header={'fontWeight': 'bold', 'backgroundColor': '#f2f2f2'},
            page_size=20,
            sort_action='native'
        )

    elif tab == 'top':
        top = merged[['name_muni', 'Empresas']].rename(columns={
            'name_muni': 'Município',
            'Empresas': 'Qtde de Empresas'
        }).sort_values(by='Qtde de Empresas', ascending=False).head(10)

        return dash_table.DataTable(
            columns=[{"name": i, "id": i} for i in top.columns],
            data=top.to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'left', 'padding': '5px'},
            style_header={'fontWeight': 'bold', 'backgroundColor': '#f2f2f2'},
            sort_action='native'
        )

    elif tab == 'analises':
        # Top 5 CNAEs por município (acumulado)
        top_cnaes = df_long.groupby('CNAE 2.0 Subclasse')['Empresas'].sum().nlargest(5).reset_index()

        fig_bar = px.bar(
            top_cnaes,
            x='CNAE 2.0 Subclasse',
            y='Empresas',
            title='🏅 Top 5 Subclasses com Mais Empresas na Paraíba',
            labels={'Empresas': 'Empresas'},
            text_auto=True,
            color='Empresas',
            color_continuous_scale='Blues'
        )
        fig_bar.update_layout(xaxis_title='Subclasse CNAE', yaxis_title='Empresas')

        return html.Div([
            dcc.Graph(figure=fig_bar)
        ])

# === RODA A APLICAÇÃO ===
if __name__ == '__main__':
    app.run(debug=True)
