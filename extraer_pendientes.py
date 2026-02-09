import firebase_admin
from firebase_admin import credentials, firestore
import csv
from datetime import datetime

# 1. Conexión a Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("claves.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def exportar_pendientes():
    print("⏳ Extrayendo consultas no entendidas con Análisis de Sentimiento...")
    
    # Referencia a la colección de fallos
    docs = db.collection('consultas_pendientes').stream()
    
    # Abrimos el archivo original 'pendientes_bacar.csv'
    with open('pendientes_bacar.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        
        # AGREGAMOS 'Sentimiento' al cabezal
        writer.writerow(['Pregunta', 'Fecha', 'Sentimiento']) 
        
        contador = 0
        for doc in docs:
            d = doc.to_dict()
            pregunta = d.get('pregunta', 'Sin datos')
            fecha = d.get('fecha')
            
            # NUEVO: Extraemos el sentimiento que ahora guarda el app.py
            # Si es una consulta vieja que no tiene sentimiento, pondrá "No analizado"
            sentimiento = d.get('sentimiento', 'No analizado')
            
            # Formateamos la fecha como ya lo hacías
            fecha_str = fecha.strftime('%d/%m/%Y') if fecha else "N/A"
            
            # ESCRIBIMOS LAS 3 COLUMNAS
            writer.writerow([pregunta, fecha_str, sentimiento])
            contador += 1
            
    print(f"✅ ¡Hecho! Se guardaron {contador} consultas en 'pendientes_bacar.csv' incluyendo análisis de tono.")

if __name__ == "__main__":
    exportar_pendientes()