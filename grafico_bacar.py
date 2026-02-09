import firebase_admin
from firebase_admin import credentials, firestore
import matplotlib.pyplot as plt

# 1. Conexión a tu Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("claves.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def crear_grafico():
    # 2. Traer datos de la colección que vimos en tu captura
    docs = db.collection('feedback_respuestas').stream()
    
    votos = {"Útil (Sí)": 0, "No Útil (No)": 0}
    
    for doc in docs:
        data = doc.to_dict()
        if data.get('fue_util') == "si":
            votos["Útil (Sí)"] += 1
        else:
            votos["No Útil (No)"] += 1

    # 3. Configurar el gráfico de torta
    labels = votos.keys()
    sizes = votos.values()
    colores = ['#4CAF50', '#FF5252'] # Verde para sí, Rojo para no
    explode = (0.1, 0)  # Resaltar la parte del "Sí"

    plt.figure(figsize=(8, 6))
    plt.pie(sizes, explode=explode, labels=labels, colors=colores, 
            autopct='%1.1f%%', shadow=True, startangle=140)
    
    plt.title("Nivel de Satisfacción - Asistente RRHH Bacar SA")
    plt.axis('equal') 
    
    print("📊 Generando gráfico de satisfacción...")
    plt.show()

if __name__ == "__main__":
    crear_grafico()