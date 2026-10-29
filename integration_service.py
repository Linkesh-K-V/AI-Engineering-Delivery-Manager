import time
import uuid
import logging
import httpx

logger = logging.getLogger(__name__)

def dispatch_to_ticketing_system(
    task_title: str,
    task_description: str,
    assignee_name: str,
    effort_hours: float
) -> str:
    """
    Simulates an external API call to a ticketing platform (like Jira or GitHub Issues)
    using simulated network latency, returning a mock ticket ID.
    """
    time.sleep(1)
    ticket_id = "TICKET-" + str(uuid.uuid4())[:6].upper()
    return ticket_id

async def send_team_notification(
    webhook_url: str,
    task_title: str,
    assignee_name: str,
    ticket_id: str
) -> bool:
    """
    Sends an asynchronous webhook notification to Slack or Microsoft Teams
    when a task is approved, returning True on success (status 200-299) and False on failure/timeout.
    """
    payload = {
        "text": f"✅ **New Task Assigned**\n**Task:** {task_title}\n**Assignee:** {assignee_name}\n**Ticket:** {ticket_id}"
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Team notification sent successfully to {webhook_url}: {response.status_code}")
            return True
    except Exception as e:
        logger.error(f"Failed to send team notification to {webhook_url}: {e}")
        return False
