from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt


NAVY = RGBColor(17, 45, 102)
BLUE = RGBColor(39, 93, 210)
GREEN = RGBColor(20, 143, 104)
LIGHT_BG = RGBColor(244, 247, 253)
WHITE = RGBColor(255, 255, 255)
GRAY = RGBColor(80, 92, 112)
DARK = RGBColor(23, 33, 53)


def style_paragraph(paragraph, size=22, bold=False, color=DARK, align=PP_ALIGN.LEFT):
    paragraph.font.name = "Calibri"
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = color
    paragraph.alignment = align


def add_background(slide):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = LIGHT_BG

    # Barra superior
    top = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        Inches(0),
        Inches(0),
        Inches(13.333),
        Inches(0.72),
    )
    top.fill.solid()
    top.fill.fore_color.rgb = NAVY
    top.line.fill.background()

    tb = slide.shapes.add_textbox(Inches(0.45), Inches(0.12), Inches(7.5), Inches(0.4))
    p = tb.text_frame.paragraphs[0]
    p.text = "BacarIT  |  Chatbot RRHH"
    style_paragraph(p, size=16, bold=True, color=WHITE)


def add_cover(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide)

    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(11.8), Inches(1.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = "CHATBOT RRHH"
    style_paragraph(p, size=44, bold=True, color=NAVY)
    p = tf.add_paragraph()
    p.text = "EL CIRCUITO DE ATENCIÓN INTELIGENTE"
    style_paragraph(p, size=28, bold=True, color=BLUE)

    subtitle = slide.shapes.add_textbox(Inches(0.9), Inches(3.5), Inches(11.2), Inches(1.5))
    stf = subtitle.text_frame
    s = stf.paragraphs[0]
    s.text = (
        "Una solución omnicanal para responder consultas de colaboradores, "
        "derivar a RRHH en tiempo real y escalar a múltiples empresas/sucursales."
    )
    style_paragraph(s, size=20, color=GRAY)

    chip = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        Inches(0.9),
        Inches(5.45),
        Inches(4.1),
        Inches(0.6),
    )
    chip.fill.solid()
    chip.fill.fore_color.rgb = GREEN
    chip.line.fill.background()
    ctf = chip.text_frame
    ctf.clear()
    cp = ctf.paragraphs[0]
    cp.text = "Estado actual: MVP operativo"
    style_paragraph(cp, size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


def add_step_slide(prs, step, title, description, points, tech_label):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide)

    badge = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        Inches(0.8),
        Inches(1.0),
        Inches(1.9),
        Inches(0.55),
    )
    badge.fill.solid()
    badge.fill.fore_color.rgb = BLUE
    badge.line.fill.background()
    btf = badge.text_frame
    btf.clear()
    bp = btf.paragraphs[0]
    bp.text = f"Paso {step}"
    style_paragraph(bp, size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.75), Inches(11.8), Inches(0.9))
    tp = title_box.text_frame.paragraphs[0]
    tp.text = title
    style_paragraph(tp, size=33, bold=True, color=NAVY)

    desc_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.7), Inches(11.7), Inches(1.0))
    dp = desc_box.text_frame.paragraphs[0]
    dp.text = description
    style_paragraph(dp, size=18, color=GRAY)

    panel = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        Inches(0.8),
        Inches(3.9),
        Inches(11.7),
        Inches(2.5),
    )
    panel.fill.solid()
    panel.fill.fore_color.rgb = WHITE
    panel.line.color.rgb = RGBColor(220, 228, 241)

    body = panel.text_frame
    body.clear()
    for idx, item in enumerate(points):
        p = body.paragraphs[0] if idx == 0 else body.add_paragraph()
        p.text = f"• {item}"
        style_paragraph(p, size=18, color=DARK)

    tech = slide.shapes.add_textbox(Inches(0.9), Inches(6.55), Inches(11.5), Inches(0.35))
    t = tech.text_frame.paragraphs[0]
    t.text = f"Tecnología principal: {tech_label}"
    style_paragraph(t, size=14, bold=True, color=GREEN)


def add_advantages_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide)

    title = slide.shapes.add_textbox(Inches(0.8), Inches(1.15), Inches(11.8), Inches(0.7))
    p = title.text_frame.paragraphs[0]
    p.text = "Ventajas Operativas y de Escalabilidad"
    style_paragraph(p, size=31, bold=True, color=NAVY)

    cards = [
        ("Capacidad", "800 a 1000 consultas/mes sin ampliar equipo base."),
        ("Disponibilidad", "Atención 24/7 con autogestión + derivación humana cuando aplica."),
        ("Trazabilidad", "Historial completo y métricas en tiempo real por empresa/sucursal."),
        ("Escalabilidad", "Arquitectura multiempresa y roles para crecer con bajo costo incremental."),
    ]

    x_positions = [0.8, 3.95, 7.1, 10.25]
    for idx, (name, desc) in enumerate(cards):
        card = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(x_positions[idx]),
            Inches(2.2),
            Inches(2.7),
            Inches(3.9),
        )
        card.fill.solid()
        card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = RGBColor(215, 226, 243)
        tf = card.text_frame
        tf.clear()
        n = tf.paragraphs[0]
        n.text = name
        style_paragraph(n, size=18, bold=True, color=BLUE, align=PP_ALIGN.CENTER)
        d = tf.add_paragraph()
        d.text = desc
        style_paragraph(d, size=14, color=DARK, align=PP_ALIGN.CENTER)


def add_stack_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide)

    title = slide.shapes.add_textbox(Inches(0.8), Inches(1.15), Inches(11.8), Inches(0.7))
    p = title.text_frame.paragraphs[0]
    p.text = "Tecnología y Arquitectura del Chatbot"
    style_paragraph(p, size=31, bold=True, color=NAVY)

    items = [
        ("Flask + Python", "API del chatbot, panel RRHH y autenticación."),
        ("Firestore", "Persistencia de conversaciones, handoff, historial y configuración."),
        ("Panel RRHH Web", "Atención humana en vivo, reasignación y cierre de casos."),
        ("RBAC + Configuración", "Usuarios, roles, permisos y gestión multiempresa/sucursal."),
        ("Cloud Ready", "Despliegue en Cloud Run/Firebase con escalabilidad administrada."),
    ]

    y = 2.1
    for name, detail in items:
        row = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(0.9),
            Inches(y),
            Inches(11.4),
            Inches(0.82),
        )
        row.fill.solid()
        row.fill.fore_color.rgb = WHITE
        row.line.color.rgb = RGBColor(219, 230, 244)
        tf = row.text_frame
        tf.clear()
        n = tf.paragraphs[0]
        n.text = f"{name}: "
        style_paragraph(n, size=16, bold=True, color=BLUE)
        d = tf.add_paragraph()
        d.text = detail
        style_paragraph(d, size=14, color=DARK)
        y += 0.95


def add_impact_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide)

    title = slide.shapes.add_textbox(Inches(0.8), Inches(1.1), Inches(11.8), Inches(0.7))
    p = title.text_frame.paragraphs[0]
    p.text = "Impacto en la Organización y Próximos Pasos"
    style_paragraph(p, size=31, bold=True, color=NAVY)

    left = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(2.0), Inches(5.7), Inches(4.1)
    )
    left.fill.solid()
    left.fill.fore_color.rgb = WHITE
    left.line.color.rgb = RGBColor(214, 225, 242)
    ltf = left.text_frame
    ltf.clear()
    lp = ltf.paragraphs[0]
    lp.text = "Impacto actual"
    style_paragraph(lp, size=20, bold=True, color=BLUE)
    for line in [
        "• Respuesta inmediata a FAQs de RRHH.",
        "• Derivación automática a agentes cuando se requiere intervención humana.",
        "• Operación por empresa/sucursal con trazabilidad completa.",
        "• Menor carga operativa para RRHH y mejor experiencia del colaborador.",
    ]:
        p = ltf.add_paragraph()
        p.text = line
        style_paragraph(p, size=15, color=DARK)

    right = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(2.0), Inches(5.7), Inches(4.1)
    )
    right.fill.solid()
    right.fill.fore_color.rgb = WHITE
    right.line.color.rgb = RGBColor(214, 225, 242)
    rtf = right.text_frame
    rtf.clear()
    rp = rtf.paragraphs[0]
    rp.text = "Próxima etapa"
    style_paragraph(rp, size=20, bold=True, color=GREEN)
    for line in [
        "• Integración con WhatsApp Business.",
        "• Ajustes de métricas por SLA y productividad de agentes.",
        "• Despliegue cloud productivo con hardening de seguridad.",
        "• Escalado a nuevas áreas y compañías del grupo.",
    ]:
        p = rtf.add_paragraph()
        p.text = line
        style_paragraph(p, size=15, color=DARK)

    footer = slide.shapes.add_textbox(Inches(0.85), Inches(6.35), Inches(11.6), Inches(0.45))
    fp = footer.text_frame.paragraphs[0]
    fp.text = (
        "Visión: consolidar un canal único, auditable y escalable para la gestión de consultas de RRHH."
    )
    style_paragraph(fp, size=14, bold=True, color=GREEN, align=PP_ALIGN.CENTER)


def build_presentation(output_path: Path):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    add_cover(prs)
    add_step_slide(
        prs,
        step=1,
        title="Recepción Inteligente de Consultas",
        description="El asistente recibe consultas por web y organiza cada interacción en tiempo real.",
        points=[
            "Ingreso de consultas frecuentes de colaboradores de forma automática.",
            "Inicio de conversación con branding dinámico por empresa.",
            "Registro estructurado de sesiones para seguimiento y analítica.",
        ],
        tech_label="Flask API + lógica conversacional (Python)",
    )
    add_step_slide(
        prs,
        step=2,
        title="Comprensión y Respuesta Automática",
        description="El motor del chatbot interpreta intención, responde FAQs y solicita feedback.",
        points=[
            "Búsqueda semántica/fuzzy sobre base de preguntas frecuentes.",
            "Manejo de sinónimos y normalización para consultas en lenguaje natural.",
            "Cierre asistido con validación de utilidad de la respuesta.",
        ],
        tech_label="Módulo chatbot + reglas de lenguaje + Firestore",
    )
    add_step_slide(
        prs,
        step=3,
        title="Derivación Humana en Vivo (Handoff RRHH)",
        description="Cuando el bot no alcanza, escala la conversación a agentes RRHH activos.",
        points=[
            "Asignación automática por carga entre agentes conectados.",
            "Toma manual y reasignación con trazabilidad de quién intervino.",
            "Mensajería en tiempo real entre colaborador y RRHH.",
        ],
        tech_label="Panel RRHH + cola de handoff + heartbeat de agentes",
    )
    add_step_slide(
        prs,
        step=4,
        title="Gestión Multiempresa y Seguridad Operativa",
        description="Administración centralizada por empresa/sucursal, usuarios, roles y permisos.",
        points=[
            "Login con selección de empresa y filtros de acceso por asignación.",
            "Configuración separada para empresas, usuarios y roles.",
            "Control RBAC para conversaciones, historial y administración.",
        ],
        tech_label="Autenticación RRHH + RBAC + configuración general",
    )
    add_step_slide(
        prs,
        step=5,
        title="Historial, Métricas y Mejora Continua",
        description="Cada conversación se registra para auditar operación y optimizar el servicio.",
        points=[
            "Historial completo de interacciones y eventos de handoff.",
            "Dashboard con KPIs operativos y seguimiento en tiempo real.",
            "Base para decisiones de capacidad y experiencia del colaborador.",
        ],
        tech_label="Firestore + panel estadísticas + exportables",
    )
    add_advantages_slide(prs)
    add_stack_slide(prs)
    add_impact_slide(prs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))


if __name__ == "__main__":
    target = Path("docs/Presentacion_Chatbot_RRHH_Bacar.pptx")
    build_presentation(target)
    print(f"Presentación generada: {target.resolve()}")
