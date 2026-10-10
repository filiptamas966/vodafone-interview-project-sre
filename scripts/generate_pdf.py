from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


SECTIONS = [
    (
        "1. Implemented design",
        "This repository implements one Flask + Gunicorn application, one PostgreSQL database, Docker Compose for local deployment, a named database volume, validation, committed inserts, and health endpoints.",
    ),
    (
        "2. Request flow",
        "Client -> Flask app -> PostgreSQL insert -> commit -> return saved record. The app validates the request, inserts the row, and closes the connection after the request finishes.",
    ),
    (
        "3. Proposed production architecture",
        "Client -> ALB -> ECS Fargate tasks in AZ-a and AZ-b -> RDS PostgreSQL Multi-AZ primary/standby (region 1) -> async cross-region replica (region 2).",
    ),
    (
        "4. Availability and redundancy",
        "Run app tasks across at least two availability zones. Keep an Application Load Balancer in front of the apps and a PostgreSQL standby in another zone. Describe recovery time and possible data loss explicitly.",
    ),
    (
        "5. Elasticity",
        "Propose an initial autoscaling policy such as minimum 2 tasks, maximum 10 tasks, and CPU target 60%. These values need load testing and are not implemented in Docker Compose.",
    ),
    (
        "6. Automation gaps",
        "Local automation is implemented in Docker Compose. Cloud deployment, autoscaling, migration automation, backup restoration, and regional recovery remain proposed follow-up work.",
    ),
]


def build_pdf(output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        spaceAfter=18,
    )
    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor="#1f2937",
        spaceBefore=12,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
    )

    story = [
        Paragraph("Timestamp Event Service Design", title_style),
        Paragraph("Interview-ready summary", body_style),
        Paragraph("Proposed production architecture:", heading_style),
        Paragraph("Client -> ALB -> ECS Fargate tasks (AZ-a + AZ-b) -> RDS PostgreSQL Multi-AZ primary/standby -> async cross-region replica.", body_style),
        Spacer(1, 10),
    ]

    for heading, body in SECTIONS:
        story.append(Paragraph(heading, heading_style))
        story.append(Paragraph(body, body_style))
        story.append(Spacer(1, 8))

    doc.build(story)


if __name__ == "__main__":
    build_pdf("docs/timestamp_design.pdf")
    print("PDF generated: docs/timestamp_design.pdf")
