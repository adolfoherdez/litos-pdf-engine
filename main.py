from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import Response
import requests
import io
import os
import concurrent.futures
from typing import Optional, List
from PIL import Image as PILImage
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter


LLAVE_SECRETA_LITOS = os.environ.get("API_KEY_LITOS")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.middleware("http")
async def verificar_api_key(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path == "/":
        return await call_next(request)
        
    if request.url.path.startswith("/api/"):
        llave_recibida = request.headers.get("X-API-KEY")
        
        if llave_recibida != LLAVE_SECRETA_LITOS:
            return Response(
                content='{"error": "Acceso denegado: API Key inválida o ausente. ¡Intento de ataque bloqueado!"}', 
                status_code=401, 
                media_type="application/json"
            )
            
    response = await call_next(request)
    return response

@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    return Response(status_code=200)

@app.get("/")
def health_check():
    return {"status": "¡Google Cloud Run Turbo está activo y BLINDADO!"}

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
    firma_url: Optional[str] = None
    evidencia_urls: List[str] = []

class PaqueteriaPayload(BaseModel):
    chofer: str
    fecha: str
    geles: int
    hieleras: int
    hieloSeco: str
    sobres: int
    bolsas: int
    paqueteria: str
    numGuia: str
    peso: str
    costo: str
    urls_evidencia: List[str] = []

def obtener_imagen_platypus(url, max_width, max_height):
    if not url: return None
    try:
        # Descargamos la imagen original
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            
            # 🔥 MAGIA 1: Abrimos la imagen con Pillow
            img_pil = PILImage.open(io.BytesIO(res.content))
            
            # 🔥 MAGIA 2: Si tiene transparencia (PNG) la pasamos a RGB normal (JPEG)
            if img_pil.mode in ("RGBA", "P"):
                img_pil = img_pil.convert("RGB")
                
            # 🔥 MAGIA 3: Redimensionamos la imagen para que no sea absurdamente gigante
            # (800x800 es resolución más que suficiente para un reporte en PDF)
            img_pil.thumbnail((1920, 1920), PILImage.Resampling.LANCZOS)
            
            # 🔥 MAGIA 4: La guardamos comprimida al 60% de calidad en la memoria RAM
            img_comprimida = io.BytesIO()
            img_pil.save(img_comprimida, format="JPEG", quality=75)
            img_comprimida.seek(0)
            
            # Ahora sí, se la pasamos a ReportLab (ya comprimida y ligerita)
            img = RLImage(img_comprimida)
            
            # Ajustamos proporciones para la hoja del PDF
            aspect = img.imageWidth / float(img.imageHeight)
            if img.imageWidth > max_width:
                img.drawWidth = max_width
                img.drawHeight = max_width / aspect
            if img.drawHeight > max_height:
                img.drawHeight = max_height
                img.drawWidth = max_height * aspect
                
            return img
    except Exception as e:
        print(f"Error procesando imagen: {e}")
        pass
    return None

@app.post("/api/generar-comprobante")
def generar_comprobante(datos: VisitaPayload):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elementos = []
    estilos = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle('Titulo', parent=estilos['Heading2'], textColor=colors.HexColor("#0149ad"))
    estilo_subtitulo = ParagraphStyle('Sub', parent=estilos['Heading3'], textColor=colors.black)
    estilo_normal = estilos['Normal']
    estilo_gps = ParagraphStyle('GPS', parent=estilos['Normal'], textColor=colors.HexColor("#1565C0"), fontName="Helvetica-Bold")

    logo_path = "logo.png"
    logo_img = RLImage(logo_path, width=80, height=80) if os.path.exists(logo_path) else Paragraph("<b>LITOS LOGÍSTICA</b>", estilo_titulo)
    
    tabla_encabezado = Table([[logo_img, Paragraph("<b>COMPROBANTE DE RECOLECCIÓN</b>", estilo_titulo)]], colWidths=[100, 350])
    tabla_encabezado.setStyle(TableStyle([('ALIGN', (1,0), (1,0), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 10))
    elementos.append(Table([['']], colWidths=[530], style=[('LINEABOVE', (0,0), (-1,-1), 2, colors.HexColor("#0149ad"))]))
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("Detalles de Operación", estilo_subtitulo))
    elementos.append(Spacer(1, 5))
    elementos.append(Paragraph(f"<b>Clínica:</b> {datos.nombre_socio}", estilo_normal))
    elementos.append(Paragraph(f"<b>No. de Socio:</b> {datos.num_socio}", estilo_normal))
    elementos.append(Paragraph(f"<b>Ubicación:</b> {datos.ciudad}, {datos.estado}", estilo_normal))
    elementos.append(Paragraph(f"<b>Recolector:</b> {datos.chofer}", estilo_normal))
    elementos.append(Paragraph(f"<b>Fecha:</b> {datos.fecha}", estilo_normal))
    elementos.append(Spacer(1, 5))
    elementos.append(Paragraph(f"Validación GPS (Llegada): {datos.gps}", estilo_gps))
    elementos.append(Spacer(1, 15))

    tabla_tiempos = Table([[f"Llegada: {datos.llegada}", f"Entrega: {datos.salida}", f"Salida: {datos.salida}"]], colWidths=[176, 176, 176])
    tabla_tiempos.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.grey), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTSIZE', (0,0), (-1,-1), 9)]))
    elementos.append(tabla_tiempos)
    elementos.append(Spacer(1, 20))

    elementos.append(Paragraph("Resumen de Muestras", estilo_subtitulo))
    elementos.append(Spacer(1, 10))
    tabla_muestras = Table([
        ['Ambiente', 'Refrigerado', 'Congelado', 'TOTAL'],
        [str(datos.amb), str(datos.ref), str(datos.con), str(datos.total)]
    ], colWidths=[100, 100, 100, 100])
    tabla_muestras.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#607D8B")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f5f5f5")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    elementos.append(tabla_muestras)
    elementos.append(Spacer(1, 15))
    elementos.append(Paragraph(f"<b>Observaciones:</b> {datos.observaciones}", estilo_normal))
    elementos.append(Spacer(1, 30))

    elementos.append(Table([['']], colWidths=[530], style=[('LINEABOVE', (0,0), (-1,-1), 1, colors.grey)]))
    elementos.append(Spacer(1, 10))
    
    if datos.firma_url:
        firma = obtener_imagen_platypus(datos.firma_url, max_width=150, max_height=80)
        if firma:
            tabla_firma = Table([[firma]], colWidths=[530])
            tabla_firma.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER')]))
            elementos.append(tabla_firma)
    else:
        elementos.append(Spacer(1, 50))
    
    tabla_linea_firma = Table([["___________________________________"], ["Firma del Químico / Responsable"]], colWidths=[530])
    tabla_linea_firma.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,1), (0,1), 'Helvetica-Bold')]))
    elementos.append(tabla_linea_firma)
    
    # 🔥 MAGIA TURBO: DESCARGAS PARALELAS CON 2GB RAM 🔥
    with concurrent.futures.ThreadPoolExecutor() as executor:
        imagenes_listas = list(executor.map(lambda u: obtener_imagen_platypus(u, 450, 550), datos.evidencia_urls))

    total_fotos = len(datos.evidencia_urls)
    for i, img in enumerate(imagenes_listas):
        if img:
            elementos.append(PageBreak())
            elementos.append(Paragraph("Anexo Fotográfico", estilo_titulo))
            elementos.append(Paragraph(f"Clínica: {datos.num_socio} | Foto {i+1} de {total_fotos}", estilo_normal))
            elementos.append(Spacer(1, 5))
            elementos.append(Table([['']], colWidths=[530], style=[('LINEABOVE', (0,0), (-1,-1), 1, colors.grey)]))
            elementos.append(Spacer(1, 20))
            tabla_foto = Table([[img]], colWidths=[530])
            tabla_foto.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER')]))
            elementos.append(tabla_foto)

    doc.build(elementos)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return Response(
        content=pdf_bytes, 
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=comprobante.pdf",
            "Access-Control-Allow-Origin": "*" # 🔥 Refuerzo manual de CORS
        }
    )

@app.post("/api/generar-paqueteria")
def generar_paqueteria(datos: PaqueteriaPayload):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elementos = []
    estilos = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle('Titulo', parent=estilos['Heading2'], textColor=colors.HexColor("#0149ad"))
    estilo_subtitulo = ParagraphStyle('Sub', parent=estilos['Heading3'], textColor=colors.black)
    estilo_normal = estilos['Normal']

    logo_path = "logo.png"
    logo_img = RLImage(logo_path, width=80, height=80) if os.path.exists(logo_path) else Paragraph("<b>LITOS</b>", estilo_titulo)
    
    tabla_encabezado = Table([[logo_img, Paragraph("<b>REPORTE DE ENVÍO LOGÍSTICO</b>", estilo_titulo)]], colWidths=[100, 350])
    tabla_encabezado.setStyle(TableStyle([('ALIGN', (1,0), (1,0), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 10))
    elementos.append(Table([['']], colWidths=[530], style=[('LINEABOVE', (0,0), (-1,-1), 2, colors.HexColor("#0149ad"))]))
    elementos.append(Spacer(1, 20))

    elementos.append(Paragraph("Información de la Ruta", estilo_subtitulo))
    elementos.append(Spacer(1, 5))
    elementos.append(Paragraph(f"<b>Colaborador:</b> {datos.chofer}", estilo_normal))
    elementos.append(Paragraph(f"<b>Fecha de Operación:</b> {datos.fecha}", estilo_normal))
    elementos.append(Spacer(1, 20))

    elementos.append(Paragraph("Desglose de Insumos", estilo_subtitulo))
    elementos.append(Spacer(1, 10))
    tabla_insumos = Table([
        ['Geles', 'Hieleras', 'Hielo Seco', 'Sobres', 'Bolsas'],
        [str(datos.geles), str(datos.hieleras), f"{datos.hieloSeco} Kg", str(datos.sobres), str(datos.bolsas)]
    ], colWidths=[100, 100, 100, 100, 100])
    
    tabla_insumos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#607D8B")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f5f5f5")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    elementos.append(tabla_insumos)
    elementos.append(Spacer(1, 25))

    if datos.paqueteria.lower() != 'local':
        elementos.append(Paragraph("Detalles de Paquetería", estilo_subtitulo))
        elementos.append(Spacer(1, 5))
        elementos.append(Paragraph(f"<b>Empresa Transportista:</b> {datos.paqueteria}", estilo_normal))
        elementos.append(Paragraph(f"<b>No. Guía:</b> {datos.numGuia}", estilo_normal))
        elementos.append(Paragraph(f"<b>Peso Registrado:</b> {datos.peso} Kg", estilo_normal))
        elementos.append(Paragraph(f"<b>Costo:</b> ${datos.costo}", estilo_normal))
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        imagenes_listas = list(executor.map(lambda u: obtener_imagen_platypus(u, 450, 550), datos.urls_evidencia))

    total_fotos = len(datos.urls_evidencia)
    for i, img in enumerate(imagenes_listas):
        if img:
            elementos.append(PageBreak())
            elementos.append(Paragraph("Anexo Fotográfico Logístico", estilo_titulo))
            elementos.append(Paragraph(f"Foto {i+1} de {total_fotos}", estilo_normal))
            elementos.append(Spacer(1, 5))
            elementos.append(Table([['']], colWidths=[530], style=[('LINEABOVE', (0,0), (-1,-1), 1, colors.grey)]))
            elementos.append(Spacer(1, 20))
            
            tabla_foto = Table([[img]], colWidths=[530])
            tabla_foto.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER')]))
            elementos.append(tabla_foto)

    doc.build(elementos)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return Response(content=pdf_bytes, media_type="application/pdf")
