import csv
from firebase_config import inicializar_firestore

# 1. Conexión con tus credenciales
db = inicializar_firestore(verbose=False)

def exportar_datos():
    if not db:
        print("⚠️ No hay conexión a Firestore. No se puede exportar feedback.")
        print("ℹ️ Definí FIREBASE_CREDENTIALS=tu-clave.json y reintentá.")
        return

    print("⏳ Extrayendo datos de feedback desde Firebase...")
    
    # Referencia a tu colección de feedback
    docs = db.collection('feedback_respuestas').stream()
    
    # Creamos el archivo CSV
    with open('reporte_feedback_bacar.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Cabeceras de las columnas
        writer.writerow(['Fecha', 'Tema', 'Fue_Util'])
        
        contador = 0
        for doc in docs:
            d = doc.to_dict()
            # Convertimos la fecha a un formato legible para Excel/Sheets
            fecha = d.get('fecha')
            if fecha:
                # Si es un objeto de Firebase, lo formateamos
                fecha_str = fecha.strftime('%Y-%m-%d %H:%M')
            else:
                fecha_str = "Sin fecha"
                
            writer.writerow([fecha_str, d.get('tema'), d.get('fue_util')])
            contador += 1
            
    print(f"✅ ¡Éxito! Se exportaron {contador} registros a 'reporte_feedback_bacar.csv'.")

if __name__ == "__main__":
    exportar_datos()