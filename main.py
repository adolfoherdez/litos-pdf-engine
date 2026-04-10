from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import Response
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import requests
import io
import concurrent.futures

app = FastAPI()

# Permitir que tu web en Flutter se comunique con este Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# El "molde" de los datos que Flutter nos va a mandar
class VisitaPayload(BaseModel):
    nombre_socio: str
    num_socio: str
    ciudad: str
    estado: str
    chofer: str
    fecha: str
    gps: str
    llegada: str
    salida: str
    amb: int
    ref: int
    con: int
    total: int
    observaciones: str
    firma_url: str | None = None
    evidencia_urls: list[str] = []

def descargar_imagen(url):
    if not url: return None
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return ImageReader(io.BytesIO(res.content))
    except:
        pass
    return None

@app.post("/api/generar-comprobante")
def generar_comprobante(datos: VisitaPayload):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # --- HOJA 1: DATOS Y FIRMA ---
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 50, "COMPROBANTE DE RECOLECCIÓN P.O.D.")
    
    c.setFont("Helvetica", 12)
    c.drawString(40, height - 90, f"Clínica: {datos.nombre_socio} (Socio: {datos.num_socio})")
    c.drawString(40, height - 110, f"Ubicación: {datos.ciudad}, {datos.estado}")
    c.drawString(40, height - 130, f"Recolector: {datos.chofer}")
    c.drawString(40, height - 150, f"Fecha: {datos.fecha}")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, height - 180, f"Validación GPS (Llegada): {datos.gps}")
    
    c.setFont("Helvetica", 12)
    c.drawString(40, height - 210, f"Horarios -> Llegada: {datos.llegada} | Salida: {datos.salida}")
    c.drawString(40, height - 240, f"Muestras -> Amb: {datos.amb} | Ref: {datos.ref} | Con: {datos.con} | TOTAL: {datos.total}")
    c.drawString(40, height - 270, f"Observaciones: {datos.observaciones}")

    if datos.firma_url:
        firma_img = descargar_imagen(datos.firma_url)
        if firma_img:
            c.drawImage(firma_img, 40, height - 400, width=150, height=80, preserveAspectRatio=True)
    
    c.drawString(40, height - 420, "___________________________________")
    c.drawString(40, height - 440, "Firma del Químico / Responsable")
    c.showPage() # Fin de la hoja 1

    # --- MAGIA: DESCARGAMOS TODAS LAS FOTOS EN MILISEGUNDOS ---
    with concurrent.futures.ThreadPoolExecutor() as executor:
        imagenes_descargadas = list(executor.map(descargar_imagen, datos.evidencia_urls))

    # --- HOJAS EXTRAS: 1 FOTO POR PÁGINA ---
    for i, img in enumerate(imagenes_descargadas):
        if img:
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, height - 50, "Anexo Fotográfico")
            c.setFont("Helvetica", 10)
            c.drawString(40, height - 70, f"Foto {i + 1} de {len(imagenes_descargadas)}")
            
            # Dibujamos la foto gigante en el centro
            c.drawImage(img, 40, 50, width=width-80, height=height-150, preserveAspectRatio=True)
            c.showPage()

    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Devolvemos el PDF listo
    return Response(content=pdf_bytes, media_type="application/pdf")