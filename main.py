from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import Response
import requests
import io
import os
from typing import Optional, List

# Librerías avanzadas de diseño en Python
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def obtener_imagen_platypus(url, max_width, max_height):
    if not url: return None
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            img_data = io.BytesIO(res.content)
            img = RLImage(img_data)
            # Calcular aspecto para que no se deforme
            aspect = img.imageWidth / float(img.imageHeight)
            if img.imageWidth > max_width:
                img.drawWidth = max_width
                img.drawHeight = max_width / aspect
            if img.drawHeight > max_height:
                img.drawHeight = max_height
                img.drawWidth = max_height * aspect
            return img
    except:
        pass
    return None

@app.post("/api/generar-comprobante")
def generar_comprobante(datos: VisitaPayload):
    buffer = io.BytesIO()
    # Configuramos los márgenes de la hoja
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elementos = []
    estilos = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle('Titulo', parent=estilos['Heading2'], textColor=colors.HexColor("#0149ad"))
    estilo_subtitulo = ParagraphStyle('Sub', parent=estilos['Heading3'], textColor=colors.black)
    estilo_normal = estilos['Normal']
    estilo_gps = ParagraphStyle('GPS', parent=estilos['Normal'], textColor=colors.HexColor("#1565C0"), fontName="Helvetica-Bold")

    # --- 1. ENCABEZADO (Logo y Título) ---
    logo_path = "logo.png" # El archivo que subiste a GitHub
    logo_img = RLImage(logo_path, width=80, height=80) if os.path.exists(logo_path) else Paragraph("<b>LITOS LOGÍSTICA</b>", estilo_titulo)
    
    tabla_encabezado = Table([
        [logo_img, Paragraph("<b>COMPROBANTE DE RECOLECCIÓN</b>", estilo_titulo)]
    ], colWidths=[100, 350])
    tabla_encabezado.setStyle(TableStyle([('ALIGN', (1,0), (1,0), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 10))
    # Línea divisoria
    elementos.append(Table([['']], colWidths=[530], style=[('LINEABOVE', (0,0), (-1,-1), 2, colors.HexColor("#0149ad"))]))
    elementos.append(Spacer(1, 10))

    # --- 2. DETALLES DE OPERACIÓN ---
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

    # --- 3. TABLA DE TIEMPOS ---
    tabla_tiempos = Table([
        [f"Llegada: {datos.llegada}", f"Entrega: {datos.salida}", f"Salida: {datos.salida}"]
    ], colWidths=[176, 176, 176])
    tabla_tiempos.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.grey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,-1), 9)
    ]))
    elementos.append(tabla_tiempos)
    elementos.append(Spacer(1, 20))

    # --- 4. TABLA DE MUESTRAS ---
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

    # --- 5. FIRMA ---
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
    
    tabla_linea_firma = Table([
        ["___________________________________"],
        ["Firma del Químico / Responsable"]
    ], colWidths=[530])
    tabla_linea_firma.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (0,1), 'Helvetica-Bold')
    ]))
    elementos.append(tabla_linea_firma)
    
    # --- 6. ANEXOS FOTOGRÁFICOS (1 por hoja) ---
    total_fotos = len(datos.evidencia_urls)
    for i, url in enumerate(datos.evidencia_urls):
        img = obtener_imagen_platypus(url, max_width=450, max_height=550)
        if img:
            elementos.append(PageBreak()) # Saltamos a una hoja nueva
            elementos.append(Paragraph("Anexo Fotográfico", estilo_titulo))
            elementos.append(Paragraph(f"Clínica: {datos.num_socio} | Foto {i+1} de {total_fotos}", estilo_normal))
            elementos.append(Spacer(1, 5))
            elementos.append(Table([['']], colWidths=[530], style=[('LINEABOVE', (0,0), (-1,-1), 1, colors.grey)]))
            elementos.append(Spacer(1, 20))
            
            # Centrar la foto
            tabla_foto = Table([[img]], colWidths=[530])
            tabla_foto.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER')]))
            elementos.append(tabla_foto)
            del img # Protegemos la RAM

    # Construir el documento
    doc.build(elementos)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return Response(content=pdf_bytes, media_type="application/pdf")
