import csv
from firebase_config import inicializar_firestore

# 1. Conexión a Firebase
db = inicializar_firestore(verbose=False)

def exportar_pendientes():
    if not db:
        print("⚠️ No hay conexión a Firestore. No se puede exportar pendientes.")
        print("ℹ️ Definí FIREBASE_CREDENTIALS=tu-clave.json y reintentá.")
        return

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