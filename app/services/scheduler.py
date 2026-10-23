from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.github_service import check_all_monitored_repositories
from app.database import get_setting

scheduler = AsyncIOScheduler()

async def scheduled_github_check():
    try:
        new_count = await check_all_monitored_repositories()
        if new_count > 0:
            print(f"[Scheduler] {new_count} novo(s) evento(s) detectado(s) e notificado(s)!")
    except Exception as e:
        print(f"[Scheduler Error] Erro durante verificação periódica: {e}")

def start_scheduler():
    interval_minutes = int(get_setting("check_interval_minutes", "5") or 5)
    scheduler.add_job(
        scheduled_github_check,
        "interval",
        minutes=interval_minutes,
        id="github_poller",
        replace_existing=True
    )
    if not scheduler.running:
        scheduler.start()
        print(f"[Scheduler] Agendador iniciado! Checando repositórios a cada {interval_minutes} minutos.")

def update_scheduler_interval(minutes: int):
    if scheduler.get_job("github_poller"):
        scheduler.reschedule_job("github_poller", trigger="interval", minutes=minutes)
        print(f"[Scheduler] Intervalo atualizado para {minutes} minutos.")
