import pandas as pd
import matplotlib
matplotlib.use('Agg')  # <--- AGGIUNGI QUESTA RIGA PER RISOLVERE L'ERRORE
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# Impostazioni stile accademico
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12, 'font.family': 'serif'})

def generate_baseline_chart():
    # Dati per la baseline (ChatDev) e le medie di GurdjDev Cold (Run 2)
    labels = ['Self-Test Pass Rate (%)', 'Token Consumption (x1000)']
    
    chatdev_data = [0.0, 250.0]  
    gurdjdev_data = [51.46, 34.4] 
    
    x = np.arange(len(labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(8, 6))
    rects1 = ax.bar(x - width/2, chatdev_data, width, label='ChatDev (Baseline)', color='#e74c3c')
    rects2 = ax.bar(x + width/2, gurdjdev_data, width, label='GurdjDev (Cold Run)', color='#2ecc71')
    
    ax.set_ylabel('Valori (Scale diverse)')
    ax.set_title('Confronto Prestazioni: Baseline Conversazionale vs Architettura Deterministica')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    
    # Aggiunge i valori sopra le barre
    ax.bar_label(rects1, padding=3)
    ax.bar_label(rects2, padding=3)
    
    fig.tight_layout()
    plt.savefig('chart_baseline.png', dpi=300, bbox_inches='tight')
    print("Grafico 1 salvato: chart_baseline.png")

def generate_memory_chart():
    # Carica i dati dai CSV
    df_cold = pd.read_csv('deveval_summary_run2.csv')
    df_warm = pd.read_csv('deveval_summary_run3.csv')
    
    # Unisce i dataframe sui progetti comuni
    df_merged = pd.merge(df_cold, df_warm, on='project_name', suffixes=('_cold', '_warm'))
    
    # Seleziona solo i progetti piu significativi (inclusi quelli con ChromaDB hits)
    projects_to_plot = ['ArXiv_digest', 'TextCNN', 'geotext', 'hone', 'lice', 'stocktrends']
    df_plot = df_merged[df_merged['project_name'].isin(projects_to_plot)]
    
    labels = df_plot['project_name']
    pass_cold = df_plot['self_test_pass_rate_cold']
    pass_warm = df_plot['self_test_pass_rate_warm']
    
    x = np.arange(len(labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    rects1 = ax.bar(x - width/2, pass_cold, width, label='Cold Run (No Memoria)', color='#3498db')
    rects2 = ax.bar(x + width/2, pass_warm, width, label='Warm Run (Con Memoria)', color='#f39c12')
    
    # Evidenzia l'intervento della memoria (senza accenti per evitare errori UTF-8)
    ax.set_ylabel('Self-Test Pass Rate (%)')
    ax.set_title("Impatto dell'Iniezione RAG sulla Qualita' del Codice (Negative & Positive Transfer)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.legend()
    
    # Annota i ChromaDB hits sulle barre della Warm Run
    for i, project in enumerate(labels):
        hits = df_plot[df_plot['project_name'] == project]['chromadb_hits_warm'].values[0]
        if hits > 0:
            ax.annotate(f'Mem Hit ({hits})',
                        xy=(x[i] + width/2, pass_warm.iloc[i]),
                        xytext=(0, 5),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, color='red', weight='bold')

    fig.tight_layout()
    plt.savefig('chart_memory.png', dpi=300, bbox_inches='tight')
    print("Grafico 2 salvato: chart_memory.png")

if __name__ == "__main__":
    try:
        generate_baseline_chart()
        generate_memory_chart()
        print("Tutti i grafici sono stati generati con successo nella directory corrente!")
    except FileNotFoundError:
        print("ERRORE: Assicurati che i file CSV siano nella stessa cartella dello script.")