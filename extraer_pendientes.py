import firebase_admin
from firebase_admin import credentials, firestore
import csv

# 1. Conexión (si ya está inicializado en otro script del mismo proceso, no hace falta repetir)
if not firebase_admin._apps:
    cred = credentials.Certificate("claves.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def exportar_pendientes():
    print("⏳ Extrayendo consultas no entendidas...")
    
    # Referencia a la colección de fallos
    docs = db.collection('consultas_pendientes').stream()
    
    with open('pendientes_bacar.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Pregunta', 'Fecha']) # Cabezal
        
        contador = 0
        for doc in docs:
            d = doc.to_dict()
            pregunta = d.get('pregunta', 'Sin datos')
            fecha = d.get('fecha')
            fecha_str = fecha.strftime('%d/%m/%Y') if fecha else "N/A"
            
            writer.writerow([pregunta, fecha_str])
            contador += 1
            
    print(f"✅ ¡Hecho! Se guardaron {contador} consultas pendientes en 'pendientes_bacar.csv'.")

if __name__ == "__main__":
    exportar_pendientes()