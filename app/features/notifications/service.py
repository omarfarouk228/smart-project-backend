import os
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.notifications.models import Notification, NotificationType

_template_dir = os.path.join(os.path.dirname(__file__), "templates")
_jinja = Environment(
    loader=FileSystemLoader(_template_dir),
    autoescape=select_autoescape(["html"]),
)


# ─── In-app notifications ─────────────────────────────────────────────────────

async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: NotificationType,
    title: str,
    body: str | None = None,
    task_id: uuid.UUID | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id, type=type, title=title, body=body, task_id=task_id
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def list_notifications(db: AsyncSession, user_id: uuid.UUID, limit: int = 50) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.is_read.asc(), Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_read(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.commit()


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id)
        .values(is_read=True)
    )
    await db.commit()


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    return result.scalar_one()


# ─── Email ────────────────────────────────────────────────────────────────────

async def send_email(
    org,
    to: str,
    subject: str,
    template_name: str,
    context: dict,
) -> bool:
    if not org.smtp_configured:
        return False
    try:
        html = _jinja.get_template(template_name).render(
            **context,
            app_name=org.app_name,
            org_name=org.name,
        )
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = org.smtp_from
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))

        await aiosmtplib.send(
            msg,
            hostname=org.smtp_host,
            port=org.smtp_port,
            username=org.smtp_user,
            password=org.smtp_password,
            use_tls=org.smtp_ssl,
        )
        return True
    except Exception:
        return False


async def send_welcome_email(org, to: str, full_name: str, password: str) -> bool:
    return await send_email(
        org=org,
        to=to,
        subject=f"Bienvenue sur {org.app_name}",
        template_name="welcome.html",
        context={
            "full_name": full_name,
            "email": to,
            "password": password,
            "login_url": f"{settings.FRONTEND_URL}/login",
        },
    )


async def send_password_reset_email(org, to: str, full_name: str, new_password: str) -> bool:
    return await send_email(
        org=org,
        to=to,
        subject=f"Réinitialisation de votre mot de passe - {org.app_name}",
        template_name="password_reset.html",
        context={
            "full_name": full_name,
            "email": to,
            "new_password": new_password,
            "login_url": f"{settings.FRONTEND_URL}/login",
        },
    )


async def send_mention_email(
    org, to: str, full_name: str, mentioner: str, task_title: str, task_url: str
) -> bool:
    return await send_email(
        org=org,
        to=to,
        subject=f"Vous avez été mentionné — {org.app_name}",
        template_name="mention.html",
        context={
            "full_name": full_name,
            "mentioner": mentioner,
            "task_title": task_title,
            "task_url": task_url,
        },
    )


async def send_assigned_email(
    org, to: str, full_name: str, assigner: str, task_title: str, task_url: str
) -> bool:
    return await send_email(
        org=org,
        to=to,
        subject=f"Vous avez été assigné à une tâche — {org.app_name}",
        template_name="assigned.html",
        context={
            "full_name": full_name,
            "assigner": assigner,
            "task_title": task_title,
            "task_url": task_url,
        },
    )
