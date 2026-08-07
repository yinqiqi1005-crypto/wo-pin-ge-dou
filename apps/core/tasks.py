from celery import shared_task


@shared_task(name="core.infrastructure_echo")
def infrastructure_echo(value):
    return value
