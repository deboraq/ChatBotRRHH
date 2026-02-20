from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt


NAVY = RGBColor(19, 50, 113)
BLUE = RGBColor(49, 104, 218)
GREEN = RGBColor(24, 157, 117)
ORANGE = RGBColor(232, 148, 32)
WHITE = RGBColor(255, 255, 255)
DARK = RGBColor(28, 38, 60)
MID = RGBColor(82, 96, 124)
BORDER = RGBColor(210, 221, 240)

BG_IMAGES = [
    Path("docs/images/chatbot-bg-1.jpg"),
    Path("docs/images/chatbot-bg-2.jpg"),
    Path("docs/images/chatbot-bg-3.jpg"),
]


def style_paragraph(paragraph, size=18, bold=False, color=DARK, align=PP_ALIGN.LEFT):
    paragraph.font.name = "Calibri"
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = color
    paragraph.font.underline = False
    paragraph.alignment = align


def clear_text_frame(tf):
    tf.clear()
    tf.word_wrap = True


def pick_bg(index):
    valid = [path for path in BG_IMAGES if path.exists()]
    if not valid:
        return None
    return valid[(index - 1) % len(valid)]


def add_background(slide, index):
    bg = pick_bg(index)
    if bg:
        slide.shapes.add_picture(str(bg), Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    else:
        fallback = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5)
        )
        fallback.fill.solid()
        fallback.fill.fore_color.rgb = RGBColor(232, 238, 250)
        fallback.line.fill.background()

    overlay = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5)
    )
    overlay.fill.solid()
    overlay.fill.fore_color.rgb = RGBColor(7, 15, 30)
    overlay.fill.transparency = 0.34
    overlay.line.fill.background()

    top = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.68)
    )
    top.fill.solid()
    top.fill.fore_color.rgb = NAVY
    top.fill.transparency = 0.08
    top.line.fill.background()

    brand = slide.shapes.add_textbox(Inches(0.5), Inches(0.12), Inches(7.8), Inches(0.35))
    p = brand.text_frame.paragraphs[0]
    p.text = "BacarIT  |  Chatbot RRHH"
    style_paragraph(p, size=16, bold=True, color=WHITE)


def add_title(slide, title, subtitle="", y=0.95):
    box = slide.shapes.add_textbox(Inches(0.75), Inches(y), Inches(12.0), Inches(1.35))
    tf = box.text_frame
    clear_text_frame(tf)
    p = tf.paragraphs[0]
    p.text = title
    style_paragraph(p, size=34, bold=True, color=WHITE)
    if subtitle:
        s = tf.add_paragraph()
        s.text = subtitle
        style_paragraph(s, size=18, color=RGBColor(230, 236, 248))


def add_card(slide, x, y, w, h, title, bullets, title_color=BLUE):
    card = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = WHITE
    card.fill.transparency = 0.05
    card.line.color.rgb = BORDER

    tf = card.text_frame
    clear_text_frame(tf)
    t = tf.paragraphs[0]
    t.text = title
    style_paragraph(t, size=20, bold=True, color=title_color)
    for bullet in bullets:
        p = tf.add_paragraph()
        p.text = f"• {bullet}"
        style_paragraph(p, size=16, color=DARK)


def add_chip(slide, text, x, y, color=GREEN):
    chip = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(5.2), Inches(0.62)
    )
    chip.fill.solid()
    chip.fill.fore_color.rgb = color
    chip.line.fill.background()
    tf = chip.text_frame
    clear_text_frame(tf)
    p = tf.paragraphs[0]
    p.text = text
    style_paragraph(p, size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


def slide_cover(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(
        slide,
        "CHATBOT RRHH",
        "Propuesta ejecutiva para mejorar la experiencia del colaborador y la productividad de RRHH",
        y=1.4,
    )
    add_card(
        slide,
        0.85,
        2.9,
        11.65,
        2.0,
        "Resumen ejecutivo",
        [
            "Atención rápida y uniforme para consultas frecuentes.",
            "Derivación directa a RRHH cuando el caso requiere intervención humana.",
            "Gestión por empresa/sucursal con trazabilidad y métricas de operación.",
        ],
    )
    add_chip(slide, "Objetivo del comité: validar presupuesto y salida productiva", 0.9, 5.35)


def slide_situation(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(slide, "Situación actual", "Hay oportunidad concreta de mejorar tiempos y calidad de atención.")
    add_card(
        slide,
        0.8,
        2.2,
        5.85,
        3.95,
        "Dolores hoy",
        [
            "Consultas repetitivas consumen tiempo del equipo.",
            "La experiencia del colaborador depende del horario.",
            "No siempre hay un circuito único para seguimiento.",
            "Se pierde foco en tareas de mayor valor para RRHH.",
        ],
        title_color=ORANGE,
    )
    add_card(
        slide,
        6.7,
        2.2,
        5.85,
        3.95,
        "Qué ganamos al resolverlo",
        [
            "Menos carga operativa en preguntas frecuentes.",
            "Respuesta más rápida y consistente.",
            "Más tiempo del equipo en casos críticos.",
            "Datos claros para gestión y mejora continua.",
        ],
        title_color=GREEN,
    )


def slide_solution(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(slide, "La propuesta", "Un canal único de atención: chatbot + atención humana integrada.")
    add_card(
        slide,
        0.8,
        2.2,
        11.7,
        1.75,
        "Qué hace el chatbot",
        [
            "Responde automáticamente consultas frecuentes.",
            "Escala a RRHH en tiempo real cuando corresponde.",
        ],
    )
    add_card(
        slide,
        0.8,
        4.15,
        3.75,
        2.0,
        "Para colaboradores",
        ["Respuesta rápida", "Canal claro", "Mejor experiencia"],
    )
    add_card(
        slide,
        4.8,
        4.15,
        3.75,
        2.0,
        "Para RRHH",
        ["Menos repetición", "Más foco", "Bandeja unificada"],
    )
    add_card(
        slide,
        8.8,
        4.15,
        3.7,
        2.0,
        "Para dirección",
        ["Métricas claras", "Escalabilidad", "Mejor productividad"],
        title_color=GREEN,
    )


def slide_journey_colaborador(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(slide, "Experiencia del colaborador", "Flujo simple y entendible en 4 pasos.")
    cols = [
        ("1) Consulta", "El colaborador escribe su necesidad."),
        ("2) Respuesta", "Recibe respuesta inmediata y guía."),
        ("3) Pase a RRHH", "Si hace falta, toma un agente humano."),
        ("4) Cierre", "Se resuelve y queda registro."),
    ]
    x = 0.85
    for name, detail in cols:
        add_card(slide, x, 2.35, 3.08, 3.6, name, [detail], title_color=BLUE)
        x += 3.15


def slide_journey_rrhh(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(slide, "Experiencia del equipo RRHH", "Gestión más ordenada, colaborativa y medible.")
    add_card(
        slide,
        0.8,
        2.15,
        11.7,
        4.2,
        "Qué cambia para RRHH",
        [
            "Conversaciones centralizadas y priorizadas.",
            "Posibilidad de tomar, reasignar y cerrar casos con registro.",
            "Operación por empresa/sucursal según permisos.",
            "Seguimiento con indicadores de tiempo y volumen.",
            "Menos trabajo administrativo, más foco en personas.",
        ],
        title_color=GREEN,
    )


def slide_capabilities(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(slide, "Capacidades de negocio ya disponibles", "")
    add_card(
        slide,
        0.8,
        2.2,
        5.8,
        4.0,
        "Operación y servicio",
        [
            "Atención inicial automática 24/7.",
            "Derivación a personas cuando el caso lo requiere.",
            "Historial centralizado de conversaciones.",
            "Dashboard de indicadores operativos.",
        ],
    )
    add_card(
        slide,
        6.7,
        2.2,
        5.8,
        4.0,
        "Escala y gobierno",
        [
            "Gestión multiempresa y multisucursal.",
            "Administración de usuarios, roles y permisos.",
            "Asignación automática y manual de conversaciones.",
            "Base lista para incorporar WhatsApp.",
        ],
        title_color=GREEN,
    )


def slide_needs(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(
        slide,
        "Qué se necesita para operar en producción",
        "Lenguaje simple para decisión ejecutiva.",
    )
    add_card(
        slide,
        0.8,
        2.2,
        3.75,
        4.0,
        "Base de datos",
        [
            "Firestore",
            "Guarda conversaciones e indicadores",
            "Permite operar por empresa/sucursal",
        ],
        title_color=BLUE,
    )
    add_card(
        slide,
        4.8,
        2.2,
        3.75,
        4.0,
        "Inteligencia",
        [
            "Google AI Studio para pruebas",
            "Gemini API para uso productivo",
            "Respuestas más precisas por contexto",
        ],
        title_color=GREEN,
    )
    add_card(
        slide,
        8.8,
        2.2,
        3.75,
        4.0,
        "Canal y operación",
        [
            "Cuenta oficial WhatsApp Business activa",
            "Número verificado y plantillas de mensajes",
            "Servidor en la nube 24/7 para continuidad",
        ],
        title_color=ORANGE,
    )


def slide_costs(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(slide, "Inversión mensual estimada (USD)", "Escenario de referencia: 800 a 1000 consultas mensuales.")

    add_card(
        slide,
        0.8,
        2.1,
        3.75,
        3.55,
        "Infraestructura + datos",
        ["USD 30 - 90 / mes", "Servidor cloud", "Base de datos Firestore"],
        title_color=BLUE,
    )
    add_card(
        slide,
        4.8,
        2.1,
        3.75,
        3.55,
        "IA (Google)",
        ["USD 60 - 180 / mes", "Uso de Gemini API", "Varía por cantidad de consultas"],
        title_color=GREEN,
    )
    add_card(
        slide,
        8.8,
        2.1,
        3.75,
        3.55,
        "WhatsApp Business",
        ["USD 80 - 250 / mes", "Depende de conversaciones y país", "Incluye proveedor oficial de canal"],
        title_color=ORANGE,
    )

    add_chip(
        slide,
        "Total estimado objetivo: USD 220 - 420 / mes | Recomendación inicial: USD 300 + 20% contingencia",
        0.9,
        5.85,
        color=NAVY,
    )
    note = slide.shapes.add_textbox(Inches(0.9), Inches(6.55), Inches(11.6), Inches(0.45))
    tf = note.text_frame
    clear_text_frame(tf)
    p = tf.paragraphs[0]
    p.text = "Base del cálculo: tarifarios públicos de Meta/Google + estimación de consumo del piloto."
    style_paragraph(p, size=13, color=WHITE, align=PP_ALIGN.CENTER)


def slide_decision(prs, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, idx)
    add_title(slide, "Decisión solicitada al Comité Ejecutivo", "")
    add_card(
        slide,
        0.8,
        2.2,
        5.85,
        4.0,
        "Aprobaciones requeridas",
        [
            "Presupuesto mensual inicial para operación.",
            "Habilitación de cuentas Google para base de datos e IA.",
            "Alta del canal oficial de WhatsApp Business.",
            "Asignación de responsable interno (RRHH + IT).",
        ],
        title_color=ORANGE,
    )
    add_card(
        slide,
        6.7,
        2.2,
        5.85,
        4.0,
        "Resultado esperado",
        [
            "Mejor experiencia del colaborador.",
            "Reducción de carga operativa de RRHH.",
            "Mayor trazabilidad y control de gestión.",
            "Escalabilidad a nuevas empresas/sucursales.",
        ],
        title_color=GREEN,
    )


def build_presentation(output_path: Path):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slide_cover(prs, 1)
    slide_situation(prs, 2)
    slide_solution(prs, 3)
    slide_journey_colaborador(prs, 4)
    slide_journey_rrhh(prs, 5)
    slide_capabilities(prs, 6)
    slide_needs(prs, 7)
    slide_costs(prs, 8)
    slide_decision(prs, 9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))


if __name__ == "__main__":
    target = Path("docs/Presentacion_Chatbot_RRHH_Bacar.pptx")
    build_presentation(target)
    print(f"Presentación generada: {target.resolve()}")
